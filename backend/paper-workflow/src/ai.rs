use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ProviderConfig {
    pub name: String,
    pub base_url: String,
    pub api_path: String,
    pub models: Vec<String>,
    #[serde(default)]
    pub requires_special_format: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AiConfig {
    pub providers: HashMap<String, ProviderConfig>,
}

impl AiConfig {
    pub fn load() -> Result<Self, String> {
        let config_path = "ai_config.json";
        let content = std::fs::read_to_string(config_path)
            .map_err(|e| format!("无法读取配置文件 {}: {}", config_path, e))?;
        serde_json::from_str(&content)
            .map_err(|e| format!("配置文件格式错误: {}", e))
    }

    pub fn get_provider(&self, key: &str) -> Option<&ProviderConfig> {
        self.providers.get(key)
    }
}

#[derive(Deserialize)]
pub struct ChatRequest {
    pub query: String,
    pub context: String,
    pub full_paper: String,
}

pub async fn call_ai_api(
    req: &ChatRequest,
    api_key: &str,
    provider_key: &str,
    model: &str,
) -> Result<String, String> {
    let config = AiConfig::load()?;

    let provider = config.get_provider(provider_key)
        .ok_or_else(|| format!("未知的AI服务提供商: {}", provider_key))?;

    let client = Client::new();
    let url = format!("{}{}", provider.base_url, provider.api_path);

    let mut full_context = String::new();

    if !req.full_paper.is_empty() {
        let paper_excerpt = if req.full_paper.len() > 30000 {
            &req.full_paper[0..30000]
        } else {
            &req.full_paper
        };
        full_context.push_str(&format!("论文内容（摘要）:\n{}\n\n", paper_excerpt));
    }

    if !req.context.is_empty() {
        full_context.push_str(&format!("划选内容:\n{}\n\n", req.context));
    }

    full_context.push_str(&format!("问题:\n{}", req.query));

    let system_prompt = "你是一个专业的学术论文助手，擅长帮助研究人员理解论文内容。请基于提供的论文内容和划选内容，准确、专业地回答用户的问题。";
    let user_content = full_context;

    let request_body = match provider_key {
        "anthropic" => {
            serde_json::json!({
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": format!("{}\n\n问题:\n{}", user_content, req.query)
                    }
                ],
                "system": system_prompt,
                "temperature": 0.7,
                "max_tokens": 2000
            })
        }
        "google" => {
            serde_json::json!({
                "contents": {
                    "role": "user",
                    "parts": [{
                        "text": format!("{}\n\n问题:\n{}", user_content, req.query)
                    }]
                },
                "system_instruction": {
                    "parts": [{
                        "text": system_prompt
                    }]
                },
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2000
                }
            })
        }
        _ => {
            serde_json::json!({
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            })
        }
    };

    let mut req = client
        .post(&url)
        .header("Authorization", format!("Bearer {}", api_key))
        .header("Content-Type", "application/json");

    if provider_key == "anthropic" {
        req = req.header("anthropic-version", "2023-06-01");
    }

    let response = req
        .json(&request_body)
        .send()
        .await
        .map_err(|e| format!("网络请求失败: {}", e))?;

    if !response.status().is_success() {
        let status = response.status();
        let error_text = response.text().await.unwrap_or_else(|_| "无法读取错误详情".to_string());
        return Err(format!("AI API返回错误 ({}): {}", status, error_text));
    }

    let response_json: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("解析响应失败: {}", e))?;

    let reply = match provider_key {
        "anthropic" => {
            response_json["content"][0]["text"]
                .as_str()
                .map(|s| s.to_string())
                .ok_or_else(|| "AI响应格式无效，缺少回复内容".to_string())?
        }
        "google" => {
            response_json["candidates"][0]["content"]["parts"][0]["text"]
                .as_str()
                .map(|s| s.to_string())
                .ok_or_else(|| "AI响应格式无效，缺少回复内容".to_string())?
        }
        _ => {
            response_json["choices"][0]["message"]["content"]
                .as_str()
                .map(|s| s.to_string())
                .ok_or_else(|| "AI响应格式无效，缺少回复内容".to_string())?
        }
    };

    Ok(reply)
}