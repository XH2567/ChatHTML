use anyhow::{Context, Result};
use parking_lot::Mutex;
use rusqlite::{params, Connection};
use std::path::Path;
use uuid::Uuid;

pub struct Database {
    conn: Mutex<Connection>,
}

impl Database {
    pub fn new<P: AsRef<Path>>(path: P) -> Result<Self> {
        let conn = Connection::open(path).context("无法打开数据库")?;
        let db = Self {
            conn: Mutex::new(conn),
        };
        db.init_schema()?;
        db.migrate_remove_api_key_fk()?;
        Ok(db)
    }

    fn init_schema(&self) -> Result<()> {
        let conn = self.conn.lock();
        conn.execute_batch(
            r#"
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_api_keys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                encrypted_api_key TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_api_keys_meta (
                user_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                source_mode TEXT NOT NULL,
                arxiv_id TEXT,
                original_name TEXT,
                archive_size INTEGER,
                errors TEXT,
                warnings TEXT,
                duration_seconds REAL,
                artifacts TEXT,
                stage_details TEXT,
                manifest TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_api_keys_user_id ON user_api_keys(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_api_keys_meta_user_id ON user_api_keys_meta(user_id);
            "#,
        )
        .context("无法初始化数据库表")?;
        Ok(())
    }

    fn migrate_remove_api_key_fk(&self) -> Result<()> {
        let conn = self.conn.lock();

        let has_fk: bool = conn
            .query_row(
                "SELECT CAST((sql LIKE '%FOREIGN KEY%') AS INTEGER) FROM sqlite_master WHERE type='table' AND name='user_api_keys'",
                [],
                |row| row.get::<_, i32>(0),
            )
            .map(|v| v != 0)
            .unwrap_or(false);

        if !has_fk {
            return Ok(());
        }

        tracing::info!("正在移除 user_api_keys 表中的外键约束...");

        conn.execute_batch(
            "
            CREATE TABLE user_api_keys_tmp (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                encrypted_api_key TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE user_api_keys_meta_tmp (
                user_id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL
            );
            ",
        )
        .context("无法创建临时表")?;

        conn.execute(
            "INSERT INTO user_api_keys_tmp SELECT id, user_id, encrypted_api_key, created_at FROM user_api_keys",
            [],
        )
        .context("无法复制API密钥数据")?;

        conn.execute(
            "INSERT INTO user_api_keys_meta_tmp SELECT user_id, provider, model FROM user_api_keys_meta",
            [],
        )
        .context("无法复制API密钥元数据")?;

        conn.execute("DROP TABLE user_api_keys", [])
            .context("无法删除旧表")?;
        conn.execute("DROP TABLE user_api_keys_meta", [])
            .context("无法删除旧元数据表")?;

        conn.execute("ALTER TABLE user_api_keys_tmp RENAME TO user_api_keys", [])
            .context("无法重命名表")?;
        conn.execute("ALTER TABLE user_api_keys_meta_tmp RENAME TO user_api_keys_meta", [])
            .context("无法重命名元数据表")?;

        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_api_keys_user_id ON user_api_keys(user_id)", [])
            .context("无法重建索引")?;
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_api_keys_meta_user_id ON user_api_keys_meta(user_id)", [])
            .context("无法重建元数据索引")?;

        tracing::info!("外键约束迁移完成");
        Ok(())
    }

    pub fn create_user(&self, username: &str, password_hash: &str) -> Result<User> {
        let conn = self.conn.lock();
        let id = Uuid::new_v4().to_string();
        let created_at = chrono::Utc::now().to_rfc3339();

        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES (?1, ?2, ?3, ?4)",
            params![id, username, password_hash, created_at],
        )
        .context("无法创建用户")?;

        Ok(User {
            id,
            username: username.to_string(),
            created_at,
        })
    }

    pub fn get_user_by_username(&self, username: &str) -> Result<Option<User>> {
        let conn = self.conn.lock();
        let mut stmt = conn
            .prepare("SELECT id, username, created_at FROM users WHERE username = ?1")
            .context("无法准备查询")?;

        let mut rows = stmt.query(params![username])?;

        if let Some(row) = rows.next()? {
            Ok(Some(User {
                id: row.get(0)?,
                username: row.get(1)?,
                created_at: row.get(2)?,
            }))
        } else {
            Ok(None)
        }
    }

    pub fn get_user_password_hash(&self, username: &str) -> Result<Option<String>> {
        let conn = self.conn.lock();
        let mut stmt = conn
            .prepare("SELECT password_hash FROM users WHERE username = ?1")
            .context("无法准备查询")?;

        let mut rows = stmt.query(params![username])?;

        if let Some(row) = rows.next()? {
            Ok(Some(row.get(0)?))
        } else {
            Ok(None)
        }
    }

    pub fn set_user_api_key(&self, user_id: &str, encrypted_key: &str, provider: &str, model: &str) -> Result<()> {
        let conn = self.conn.lock();
        let created_at = chrono::Utc::now().to_rfc3339();

        conn.execute(
            "DELETE FROM user_api_keys WHERE user_id = ?1",
            params![user_id],
        )
        .context("无法清除旧API密钥")?;

        let id = Uuid::new_v4().to_string();
        conn.execute(
            "INSERT INTO user_api_keys (id, user_id, encrypted_api_key, created_at) VALUES (?1, ?2, ?3, ?4)",
            params![id, user_id, encrypted_key, created_at],
        )
        .context("无法保存API密钥")?;

        conn.execute(
            "INSERT OR REPLACE INTO user_api_keys_meta (user_id, provider, model) VALUES (?1, ?2, ?3)",
            params![user_id, provider, model],
        )
        .context("无法保存API密钥元数据")?;
        Ok(())
    }

    pub fn get_user_api_key(&self, user_id: &str) -> Result<Option<String>> {
        let conn = self.conn.lock();
        let mut stmt = conn
            .prepare("SELECT encrypted_api_key FROM user_api_keys WHERE user_id = ?1")
            .context("无法准备查询")?;

        let mut rows = stmt.query(params![user_id])?;

        if let Some(row) = rows.next()? {
            Ok(Some(row.get(0)?))
        } else {
            Ok(None)
        }
    }

    pub fn get_user_api_provider(&self, user_id: &str) -> Result<Option<String>> {
        let conn = self.conn.lock();
        let mut stmt = conn
            .prepare("SELECT provider FROM user_api_keys_meta WHERE user_id = ?1")
            .context("无法准备查询")?;

        let mut rows = stmt.query(params![user_id])?;

        if let Some(row) = rows.next()? {
            Ok(Some(row.get(0)?))
        } else {
            Ok(None)
        }
    }

    pub fn get_user_api_model(&self, user_id: &str) -> Result<Option<String>> {
        let conn = self.conn.lock();
        let mut stmt = conn
            .prepare("SELECT model FROM user_api_keys_meta WHERE user_id = ?1")
            .context("无法准备查询")?;

        let mut rows = stmt.query(params![user_id])?;

        if let Some(row) = rows.next()? {
            Ok(Some(row.get(0)?))
        } else {
            Ok(None)
        }
    }

    pub fn delete_user_api_key(&self, user_id: &str) -> Result<()> {
        let conn = self.conn.lock();
        conn.execute(
            "DELETE FROM user_api_keys WHERE user_id = ?1",
            params![user_id],
        )
        .context("无法删除API密钥")?;
        conn.execute(
            "DELETE FROM user_api_keys_meta WHERE user_id = ?1",
            params![user_id],
        )
        .context("无法删除API密钥元数据")?;
        Ok(())
    }
}

#[derive(Debug, Clone)]
pub struct User {
    pub id: String,
    pub username: String,
    pub created_at: String,
}