use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct LoginRequest {
    pub password: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct LoginResponse {
    pub success: bool,
    pub token: String,
    pub message: String,
}

pub fn verify_password(password: &str) -> bool {
    let admin_pass = std::env::var("ADMIN_PASSWORD").unwrap_or_else(|_| {
        // Fallback: if not set, auth is disabled (for local dev)
        "".to_string()
    });

    !admin_pass.is_empty() && password == admin_pass
}

pub fn generate_token() -> String {
    use uuid::Uuid;
    format!("token_{}", Uuid::new_v4())
}

pub fn verify_token(token: &str) -> bool {
    token.starts_with("token_") && token.len() > 40
}
