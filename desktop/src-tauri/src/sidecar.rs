// Python 后端 sidecar 管理

use std::path::PathBuf;
use std::process::Command;
use std::time::Duration;
use tauri::AppHandle;

fn candidate_cli_paths() -> Vec<PathBuf> {
    vec![
        PathBuf::from("../backend/cli.py"),
        PathBuf::from("../../backend/cli.py"),
        PathBuf::from("backend/cli.py"),
    ]
}

fn find_backend_cli() -> Option<PathBuf> {
    candidate_cli_paths().into_iter().find(|p| p.exists())
}

fn spawn_dev_backend() -> bool {
    let Some(cli_path) = find_backend_cli() else {
        return false;
    };

    // Try python3 first, then python.
    let py3 = Command::new("python3")
        .arg(&cli_path)
        .arg("serve")
        .arg("--sidecar")
        .spawn();
    if py3.is_ok() {
        return true;
    }

    Command::new("python")
        .arg(cli_path)
        .arg("serve")
        .arg("--sidecar")
        .spawn()
        .is_ok()
}

pub async fn launch_backend(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    use tauri_plugin_shell::ShellExt;

    let shell = app.shell();
    let mut launched = false;

    // 1) Release path: bundled sidecar binary.
    if let Ok(sidecar_cmd) = shell.sidecar("python-backend") {
        if sidecar_cmd.args(["serve", "--sidecar"]).spawn().is_ok() {
            launched = true;
        }
    }

    // 2) Dev path fallback: spawn backend/cli.py directly.
    if !launched {
        launched = spawn_dev_backend();
    }

    if !launched {
        return Err("Failed to launch backend sidecar (both bundled and dev fallback)".into());
    }

    // Wait for backend to be ready.
    for _ in 0..30 {
        tokio::time::sleep(Duration::from_secs(1)).await;
        match reqwest::get("http://localhost:3716/api/health").await {
            Ok(resp) if resp.status().is_success() => {
                println!("Python backend is ready");
                return Ok(());
            }
            _ => continue,
        }
    }

    Err("Backend failed to start within 30 seconds".into())
}
