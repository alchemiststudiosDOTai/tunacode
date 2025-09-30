use tunacode_core::tunacodeAuth;
use std::path::Path;
use std::sync::LazyLock;
use std::sync::RwLock;

use tunacode_core::token_data::TokenData;

static CHATGPT_TOKEN: LazyLock<RwLock<Option<TokenData>>> = LazyLock::new(|| RwLock::new(None));

pub fn get_chatgpt_token_data() -> Option<TokenData> {
    CHATGPT_TOKEN.read().ok()?.clone()
}

pub fn set_chatgpt_token_data(value: TokenData) {
    if let Ok(mut guard) = CHATGPT_TOKEN.write() {
        *guard = Some(value);
    }
}

/// Initialize the ChatGPT token from auth.json file
pub async fn init_chatgpt_token_from_auth(tunacode_home: &Path) -> std::io::Result<()> {
    let auth = tunacodeAuth::from_tunacode_home(tunacode_home)?;
    if let Some(auth) = auth {
        let token_data = auth.get_token_data().await?;
        set_chatgpt_token_data(token_data);
    }
    Ok(())
}
