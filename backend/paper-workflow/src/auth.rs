use crate::database::Database;
use anyhow::Result;
use argon2::{
    password_hash::{rand_core::OsRng, PasswordHash, PasswordHasher, PasswordVerifier, SaltString},
    Argon2,
};
use jsonwebtoken::{decode, encode, DecodingKey, EncodingKey, Header, Validation};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

const JWT_SECRET: &[u8] = b"paper_workflow_secret_key_change_in_production";
const JWT_EXPIRY_DAYS: i64 = 7;

#[derive(Debug, Serialize, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub exp: i64,
    pub iat: i64,
}

pub struct AuthService {
    pub db: Arc<Database>,
}

impl AuthService {
    pub fn new(db: Arc<Database>) -> Self {
        Self { db }
    }

    pub fn hash_password(&self, password: &str) -> Result<String> {
        let salt = SaltString::generate(&mut OsRng);
        let argon2 = Argon2::default();
        let password_hash = argon2
            .hash_password(password.as_bytes(), &salt)
            .map_err(|e| anyhow::anyhow!("无法生成密码哈希: {}", e))?;
        Ok(password_hash.to_string())
    }

    pub fn verify_password(&self, password: &str, hash: &str) -> Result<bool> {
        let parsed_hash = PasswordHash::new(hash)
            .map_err(|e| anyhow::anyhow!("无法解析密码哈希格式: {}", e))?;
        Ok(Argon2::default()
            .verify_password(password.as_bytes(), &parsed_hash)
            .is_ok())
    }

    pub fn create_token(&self, user_id: &str) -> Result<String> {
        let now = chrono::Utc::now().timestamp();
        let expiry = now + (JWT_EXPIRY_DAYS * 24 * 60 * 60);

        let claims = Claims {
            sub: user_id.to_string(),
            exp: expiry,
            iat: now,
        };

        let token = encode(
            &Header::default(),
            &claims,
            &EncodingKey::from_secret(JWT_SECRET),
        )
        .map_err(|e| anyhow::anyhow!("无法创建JWT令牌: {}", e))?;
        Ok(token)
    }

    pub fn validate_token(&self, token: &str) -> Result<Claims> {
        let token_data = decode::<Claims>(
            token,
            &DecodingKey::from_secret(JWT_SECRET),
            &Validation::default(),
        )
        .map_err(|e| anyhow::anyhow!("无效的JWT令牌: {}", e))?;
        Ok(token_data.claims)
    }

    pub fn simple_encrypt(&self, api_key: &str) -> String {
        let salt = SaltString::generate(&mut OsRng);
        let argon2 = Argon2::default();
        let hash = argon2
            .hash_password(api_key.as_bytes(), &salt)
            .expect("无法加密API密钥");
        format!("{}:{}", salt.as_str(), hash.to_string())
    }
}

pub struct AppAuth {
    pub auth_service: AuthService,
}

impl AppAuth {
    pub fn new(db: Arc<Database>) -> Self {
        let auth_service = AuthService::new(db);
        Self { auth_service }
    }
}