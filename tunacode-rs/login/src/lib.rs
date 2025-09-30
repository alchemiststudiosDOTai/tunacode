mod device_code_auth;
mod pkce;
mod server;

pub use device_code_auth::run_device_code_login;
pub use server::LoginServer;
pub use server::ServerOptions;
pub use server::ShutdownHandle;
pub use server::run_login_server;

// Re-export commonly used auth types and helpers from tunacode-core for compatibility
pub use tunacode_core::AuthManager;
pub use tunacode_core::auth::AuthDotJson;
pub use tunacode_core::auth::CLIENT_ID;
pub use tunacode_core::auth::OPENAI_API_KEY_ENV_VAR;
pub use tunacode_core::auth::get_auth_file;
pub use tunacode_core::auth::login_with_api_key;
pub use tunacode_core::auth::logout;
pub use tunacode_core::auth::try_read_auth_json;
pub use tunacode_core::auth::write_auth_json;
pub use tunacode_core::token_data::TokenData;
pub use tunacode_core::tunacodeAuth;
pub use tunacode_protocol::mcp_protocol::AuthMode;
