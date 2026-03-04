// ClawChain Desktop — Tauri 2.0 主入口
// 系统托盘 + Python 后端 sidecar + 全局快捷键 + 原生通知

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod sidecar;
mod tray;

use tauri::Manager;

#[tauri::command]
fn get_backend_url() -> String {
    "http://localhost:3716".to_string()
}

#[tauri::command]
fn get_frontend_url() -> String {
    "http://localhost:3717".to_string()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))
        .invoke_handler(tauri::generate_handler![
            get_backend_url,
            get_frontend_url,
        ])
        .setup(|app| {
            let handle = app.handle().clone();

            // Setup system tray
            tray::setup_tray(&handle)?;

            // Launch Python backend sidecar
            tauri::async_runtime::spawn(async move {
                if let Err(e) = sidecar::launch_backend(&handle).await {
                    eprintln!("Failed to launch Python backend: {}", e);
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            // Hide window instead of closing (keep running in tray)
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                window.hide().unwrap_or_default();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running ClawChain");
}
