#![allow(clippy::expect_used)]
use std::path::Path;
use tempfile::TempDir;
use wiremock::MockServer;

pub struct TesttunacodeExecBuilder {
    home: TempDir,
    cwd: TempDir,
}

impl TesttunacodeExecBuilder {
    pub fn cmd(&self) -> assert_cmd::Command {
        let mut cmd = assert_cmd::Command::cargo_bin("tunacode-exec")
            .expect("should find binary for tunacode-exec");
        cmd.current_dir(self.cwd.path())
            .env("tunacode_HOME", self.home.path())
            .env("OPENAI_API_KEY", "dummy");
        cmd
    }
    pub fn cmd_with_server(&self, server: &MockServer) -> assert_cmd::Command {
        let mut cmd = self.cmd();
        let base = format!("{}/v1", server.uri());
        cmd.env("OPENAI_BASE_URL", base);
        cmd
    }

    pub fn cwd_path(&self) -> &Path {
        self.cwd.path()
    }
    pub fn home_path(&self) -> &Path {
        self.home.path()
    }
}

pub fn test_tunacode_exec() -> TesttunacodeExecBuilder {
    TesttunacodeExecBuilder {
        home: TempDir::new().expect("create temp home"),
        cwd: TempDir::new().expect("create temp cwd"),
    }
}
