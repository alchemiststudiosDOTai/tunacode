use std::mem::swap;
use std::sync::Arc;

use tunacode_core::tunacodeAuth;
use tunacode_core::tunacodeConversation;
use tunacode_core::ConversationManager;
use tunacode_core::ModelProviderInfo;
use tunacode_core::NewConversation;
use tunacode_core::built_in_model_providers;
use tunacode_core::config::Config;
use tunacode_core::protocol::SessionConfiguredEvent;
use tempfile::TempDir;

use crate::load_default_config_for_test;

type ConfigMutator = dyn FnOnce(&mut Config);

pub struct TesttunacodeBuilder {
    config_mutators: Vec<Box<ConfigMutator>>,
}

impl TesttunacodeBuilder {
    pub fn with_config<T>(mut self, mutator: T) -> Self
    where
        T: FnOnce(&mut Config) + 'static,
    {
        self.config_mutators.push(Box::new(mutator));
        self
    }

    pub async fn build(&mut self, server: &wiremock::MockServer) -> anyhow::Result<Testtunacode> {
        // Build config pointing to the mock server and spawn tunacode.
        let model_provider = ModelProviderInfo {
            base_url: Some(format!("{}/v1", server.uri())),
            ..built_in_model_providers()["openai"].clone()
        };
        let home = TempDir::new()?;
        let cwd = TempDir::new()?;
        let mut config = load_default_config_for_test(&home);
        config.cwd = cwd.path().to_path_buf();
        config.model_provider = model_provider;
        let mut mutators = vec![];
        swap(&mut self.config_mutators, &mut mutators);

        for mutator in mutators {
            mutator(&mut config)
        }
        let conversation_manager = ConversationManager::with_auth(tunacodeAuth::from_api_key("dummy"));
        let NewConversation {
            conversation,
            session_configured,
            ..
        } = conversation_manager.new_conversation(config).await?;

        Ok(Testtunacode {
            home,
            cwd,
            tunacode: conversation,
            session_configured,
        })
    }
}

pub struct Testtunacode {
    pub home: TempDir,
    pub cwd: TempDir,
    pub tunacode: Arc<tunacodeConversation>,
    pub session_configured: SessionConfiguredEvent,
}

pub fn test_tunacode() -> TesttunacodeBuilder {
    TesttunacodeBuilder {
        config_mutators: vec![],
    }
}
