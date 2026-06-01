/**
 * Cloudflare Worker for TikTok Streak Auto Dashboard & API
 * Bound D1 Database: DB
 */

const API_KEY = "nadh_tiktok_streak_2026_api_key"; // Thay đổi khóa bảo mật của bạn ở đây

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // --- CẤU HÌNH CORS HEADERS ---
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, x-api-key, Authorization",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    // --- 1. RENDER HTML DASHBOARD (GET / hoặc /index.php) ---
    if (path === "/" || path === "/index.php" || path === "/index.html") {
      return new Response(getHTMLPage(), {
        headers: { "Content-Type": "text/html; charset=UTF-8", ...corsHeaders }
      });
    }

    // --- 2. XỬ LÝ CÁC API ENDPOINTS (/api.php hoặc /api) ---
    if (path === "/api.php" || path === "/api") {
      // Xác thực API Key
      const receivedKey = request.headers.get("x-api-key") || url.searchParams.get("api_key");
      if (!receivedKey || receivedKey !== API_KEY) {
        return new Response(JSON.stringify({ status: "error", message: "Truy cập bị từ chối. API Key không hợp lệ." }), {
          status: 401,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      const action = url.searchParams.get("action");

      try {
        switch (action) {
          case "get_contacts": {
            const { results } = await env.DB.prepare(
              "SELECT * FROM tiktok_contacts ORDER BY enabled DESC, username ASC"
            ).all();
            
            // Format trường aliases từ string sang JSON array cho frontend
            const formatted = results.map(c => {
              let aliases = [];
              if (c.aliases) {
                try {
                  aliases = JSON.parse(c.aliases);
                } catch(e) {
                  aliases = [];
                }
              }
              return {
                ...c,
                aliases: Array.isArray(aliases) ? aliases : [],
                enabled: c.enabled === 1,
                success_count: Number(c.success_count || 0),
                failure_count: Number(c.failure_count || 0)
              };
            });

            return new Response(JSON.stringify(formatted), {
              headers: { "Content-Type": "application/json", ...corsHeaders }
            });
          }

          case "save_contacts": {
            if (request.method !== "POST") {
              return new Response(JSON.stringify({ status: "error", message: "Yêu cầu POST được chấp nhận." }), {
                status: 405,
                headers: { "Content-Type": "application/json", ...corsHeaders }
              });
            }

            const contacts = await request.json();
            if (!Array.isArray(contacts)) {
              return new Response(JSON.stringify({ status: "error", message: "Dữ liệu JSON không hợp lệ." }), {
                status: 400,
                headers: { "Content-Type": "application/json", ...corsHeaders }
              });
            }

            // D1 SQLite Batch statement để chạy giao dịch tốc độ cao
            const statements = [];
            const upsertSql = `
              INSERT INTO tiktok_contacts (
                username, display_name, aliases, profile_url, user_id, sec_uid, 
                conversation_id, last_resolved_at, resolve_confidence, 
                last_sent, last_sent_at, success_count, failure_count, enabled
              ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14)
              ON CONFLICT(username) DO UPDATE SET
                display_name = excluded.display_name,
                aliases = excluded.aliases,
                profile_url = excluded.profile_url,
                user_id = excluded.user_id,
                sec_uid = excluded.sec_uid,
                conversation_id = excluded.conversation_id,
                last_resolved_at = excluded.last_resolved_at,
                resolve_confidence = excluded.resolve_confidence,
                last_sent = excluded.last_sent,
                last_sent_at = excluded.last_sent_at,
                success_count = excluded.success_count,
                failure_count = excluded.failure_count,
                enabled = excluded.enabled
            `;

            for (const c of contacts) {
              if (!c.username) continue;
              const aliasesStr = c.aliases ? JSON.stringify(c.aliases) : "[]";
              const enabledVal = c.enabled ? 1 : 0;
              
              statements.push(
                env.DB.prepare(upsertSql).bind(
                  c.username,
                  c.display_name || c.username,
                  aliasesStr,
                  c.profile_url || null,
                  c.user_id || null,
                  c.sec_uid || null,
                  c.conversation_id || null,
                  c.last_resolved_at || null,
                  c.resolve_confidence || "low",
                  c.last_sent || null,
                  c.last_sent_at || null,
                  Number(c.success_count || 0),
                  Number(c.failure_count || 0),
                  enabledVal
                )
              );
            }

            if (statements.length > 0) {
              await env.DB.batch(statements);
            }

            return new Response(JSON.stringify({ status: "success", message: "Đồng bộ danh sách thành công." }), {
              headers: { "Content-Type": "application/json", ...corsHeaders }
            });
          }

          case "toggle_contact": {
            const username = url.searchParams.get("username");
            const enabled = url.searchParams.get("enabled") === "1" ? 1 : 0;

            if (!username) {
              return new Response(JSON.stringify({ status: "error", message: "Thiếu username." }), {
                status: 400,
                headers: { "Content-Type": "application/json", ...corsHeaders }
              });
            }

            await env.DB.prepare("UPDATE tiktok_contacts SET enabled = ?1 WHERE username = ?2")
              .bind(enabled, username)
              .run();

            return new Response(JSON.stringify({ status: "success", message: `Đã ${enabled ? "bật" : "tắt"} liên hệ @${username}` }), {
              headers: { "Content-Type": "application/json", ...corsHeaders }
            });
          }

          case "add_contact": {
            let username = url.searchParams.get("username") || "";
            const displayName = url.searchParams.get("display_name") || "";

            if (username.startsWith("@")) {
              username = username.substring(1);
            }

            if (!username) {
              return new Response(JSON.stringify({ status: "error", message: "Thiếu username." }), {
                status: 400,
                headers: { "Content-Type": "application/json", ...corsHeaders }
              });
            }

            // Kiểm tra trùng lặp
            const existing = await env.DB.prepare("SELECT id FROM tiktok_contacts WHERE username = ?1")
              .bind(username)
              .first();

            if (existing) {
              return new Response(JSON.stringify({ status: "error", message: `Tài khoản @${username} đã tồn tại.` }), {
                status: 400,
                headers: { "Content-Type": "application/json", ...corsHeaders }
              });
            }

            const profileUrl = `https://www.tiktok.com/@${username}`;
            await env.DB.prepare(
              "INSERT INTO tiktok_contacts (username, display_name, profile_url, aliases, enabled) VALUES (?1, ?2, ?3, '[]', 1)"
            ).bind(username, displayName || username, profileUrl).run();

            return new Response(JSON.stringify({ status: "success", message: "Đã thêm bạn bè thành công." }), {
              headers: { "Content-Type": "application/json", ...corsHeaders }
            });
          }

          case "delete_contact": {
            const username = url.searchParams.get("username");
            if (!username) {
              return new Response(JSON.stringify({ status: "error", message: "Thiếu username." }), {
                status: 400,
                headers: { "Content-Type": "application/json", ...corsHeaders }
              });
            }

            await env.DB.prepare("DELETE FROM tiktok_contacts WHERE username = ?1")
              .bind(username)
              .run();

            return new Response(JSON.stringify({ status: "success", message: `Đã xoá liên hệ @${username}` }), {
              headers: { "Content-Type": "application/json", ...corsHeaders }
            });
          }

          case "update_aliases": {
            const username = url.searchParams.get("username");
            const aliasesRaw = url.searchParams.get("aliases") || "";

            if (!username) {
              return new Response(JSON.stringify({ status: "error", message: "Thiếu username." }), {
                status: 400,
                headers: { "Content-Type": "application/json", ...corsHeaders }
              });
            }

            let aliasesJson = "[]";
            try {
              const parts = aliasesRaw.split(",").map(p => p.trim()).filter(p => p.length > 0);
              aliasesJson = JSON.stringify(parts);
            } catch(e) {
              aliasesJson = "[]";
            }

            await env.DB.prepare("UPDATE tiktok_contacts SET aliases = ?1 WHERE username = ?2")
              .bind(aliasesJson, username)
              .run();

            return new Response(JSON.stringify({ status: "success", message: "Cập nhật biệt hiệu phụ thành công." }), {
              headers: { "Content-Type": "application/json", ...corsHeaders }
            });
          }

          default:
            return new Response(JSON.stringify({ status: "error", message: "Hành động không hợp lệ." }), {
              status: 400,
              headers: { "Content-Type": "application/json", ...corsHeaders }
            });
        }
      } catch (err) {
        return new Response(JSON.stringify({ status: "error", message: err.message }), {
          status: 500,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }
    }

    return new Response("Not Found", { status: 404 });
  }
};

// --- HÀM TRẢ VỀ HTML DASHBOARD FRONTEND ---
function getHTMLPage() {
  return `<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TikTok Streak Bot Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #030712;
            --panel-bg: rgba(17, 24, 39, 0.7);
            --panel-border: rgba(255, 255, 255, 0.08);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-gradient: linear-gradient(135deg, #8b5cf6, #3b82f6);
            --accent-color: #8b5cf6;
            --success-color: #10b981;
            --error-color: #ef4444;
            --warning-color: #f59e0b;
            --font-family: 'Outfit', sans-serif;
            --transition-speed: 0.3s;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: var(--font-family);
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(at 0% 0%, rgba(139, 92, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(59, 130, 246, 0.12) 0px, transparent 50%);
            background-attachment: fixed;
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem 1rem;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .container { width: 100%; max-width: 1000px; display: flex; flex-direction: column; gap: 1.5rem; }
        .glass-panel {
            background: var(--panel-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--panel-border);
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }
        header.glass-panel { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }
        .logo-section { display: flex; align-items: center; gap: 0.75rem; }
        .logo-icon {
            width: 40px; height: 40px;
            background: var(--accent-gradient);
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4);
        }
        .logo-icon svg { width: 24px; height: 24px; fill: white; }
        .logo-title h1 {
            font-size: 1.5rem; font-weight: 700;
            background: linear-gradient(to right, #ffffff, #9ca3af);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .logo-title p { font-size: 0.8rem; color: var(--text-secondary); }
        .header-actions { display: flex; gap: 0.75rem; }
        .btn {
            font-family: var(--font-family);
            display: inline-flex; align-items: center; gap: 0.5rem;
            padding: 0.6rem 1.2rem; border-radius: 8px;
            font-weight: 500; font-size: 0.9rem; cursor: pointer;
            transition: all var(--transition-speed) ease; border: none; text-decoration: none;
        }
        .btn-primary { background: var(--accent-gradient); color: white; box-shadow: 0 4px 12px rgba(139, 92, 246, 0.2); }
        .btn-primary:hover { opacity: 0.9; transform: translateY(-1px); box-shadow: 0 6px 15px rgba(139, 92, 246, 0.3); }
        .btn-secondary { background: rgba(255, 255, 255, 0.08); color: var(--text-primary); border: 1px solid var(--panel-border); }
        .btn-secondary:hover { background: rgba(255, 255, 255, 0.15); transform: translateY(-1px); }
        .btn-danger { background: rgba(239, 68, 68, 0.15); color: var(--error-color); border: 1px solid rgba(239, 68, 68, 0.2); }
        .btn-danger:hover { background: rgba(239, 68, 68, 0.25); transform: translateY(-1px); }
        .btn-icon { padding: 0.5rem; border-radius: 6px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
        .stat-card { display: flex; flex-direction: column; gap: 0.25rem; }
        .stat-label { font-size: 0.85rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; }
        .stat-value { font-size: 1.8rem; font-weight: 700; color: white; }
        .stat-value.success { color: var(--success-color); }
        .dashboard-body { overflow: hidden; display: flex; flex-direction: column; gap: 1rem; }
        .panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
        .panel-title { font-size: 1.1rem; font-weight: 600; }
        .table-container { width: 100%; overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.95rem; }
        th { padding: 1rem; font-weight: 600; color: var(--text-secondary); border-bottom: 1px solid var(--panel-border); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
        td { padding: 1rem; border-bottom: 1px solid rgba(255, 255, 255, 0.03); vertical-align: middle; }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background-color: rgba(255, 255, 255, 0.01); }
        .user-info { display: flex; flex-direction: column; gap: 0.2rem; }
        .user-name { font-weight: 600; color: white; }
        .user-handle { font-size: 0.8rem; color: var(--text-secondary); text-decoration: none; display: inline-flex; align-items: center; gap: 0.25rem; }
        .user-handle:hover { color: var(--accent-color); }
        .user-handle svg { width: 12px; height: 12px; fill: currentColor; }
        .switch { position: relative; display: inline-block; width: 44px; height: 24px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(255, 255, 255, 0.1); transition: .4s; border-radius: 24px; border: 1px solid var(--panel-border); }
        .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
        input:checked + .slider { background: var(--accent-gradient); }
        input:checked + .slider:before { transform: translateX(20px); }
        .badge { display: inline-flex; align-items: center; padding: 0.25rem 0.6rem; border-radius: 50px; font-size: 0.75rem; font-weight: 600; }
        .badge-success { background-color: rgba(16, 185, 129, 0.15); color: var(--success-color); border: 1px solid rgba(16, 185, 129, 0.2); }
        .badge-error { background-color: rgba(239, 68, 68, 0.15); color: var(--error-color); border: 1px solid rgba(239, 68, 68, 0.2); }
        .badge-warning { background-color: rgba(245, 158, 11, 0.15); color: var(--warning-color); border: 1px solid rgba(245, 158, 11, 0.2); }
        .aliases-container { display: flex; flex-wrap: wrap; gap: 0.25rem; max-width: 250px; }
        .alias-tag { background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 4px; padding: 0.15rem 0.4rem; font-size: 0.75rem; color: var(--text-secondary); }
        .action-cell { display: flex; gap: 0.5rem; }
        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0, 0, 0, 0.6); backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; opacity: 0; pointer-events: none; transition: all 0.3s ease; z-index: 1000; }
        .modal-overlay.active { opacity: 1; pointer-events: auto; }
        .modal-card { background: rgba(17, 24, 39, 0.95); border: 1px solid var(--panel-border); border-radius: 16px; width: 90%; max-width: 450px; padding: 1.5rem; box-shadow: 0 20px 40px rgba(0,0,0,0.5); transform: scale(0.9); transition: all 0.3s ease; }
        .modal-overlay.active .modal-card { transform: scale(1); }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; }
        .modal-title { font-size: 1.2rem; font-weight: 600; }
        .modal-close { background: none; border: none; color: var(--text-secondary); font-size: 1.5rem; cursor: pointer; line-height: 1; }
        .form-group { display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 1rem; }
        .form-group label { font-size: 0.85rem; font-weight: 500; color: var(--text-secondary); }
        .form-input { background-color: rgba(255, 255, 255, 0.04); border: 1px solid var(--panel-border); border-radius: 8px; padding: 0.7rem; color: white; font-family: var(--font-family); font-size: 0.9rem; outline: none; transition: all var(--transition-speed) ease; }
        .form-input:focus { border-color: var(--accent-color); background-color: rgba(255, 255, 255, 0.08); box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.2); }
        .form-help { font-size: 0.75rem; color: var(--text-secondary); }
        .modal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.5rem; }
        .toast-container { position: fixed; bottom: 2rem; right: 2rem; display: flex; flex-direction: column; gap: 0.5rem; z-index: 2000; max-width: 350px; }
        .toast { background: rgba(17, 24, 39, 0.9); backdrop-filter: blur(8px); border-left: 4px solid var(--accent-color); border-top: 1px solid var(--panel-border); border-right: 1px solid var(--panel-border); border-bottom: 1px solid var(--panel-border); border-radius: 0 8px 8px 0; padding: 1rem; color: white; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 12px rgba(0,0,0,0.3); transform: translateY(100px); opacity: 0; transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
        .toast.show { transform: translateY(0); opacity: 1; }
        .toast.success { border-left-color: var(--success-color); }
        .toast.error { border-left-color: var(--error-color); }
        .toast-content { font-size: 0.85rem; }
        @media (max-width: 768px) {
            header.glass-panel { flex-direction: column; align-items: flex-start; }
            .header-actions { width: 100%; justify-content: space-between; }
            table, thead, tbody, th, td, tr { display: block; }
            thead tr { position: absolute; top: -9999px; left: -9999px; }
            tr { border: 1px solid var(--panel-border); border-radius: 12px; margin-bottom: 1rem; padding: 0.5rem; background-color: rgba(255, 255, 255, 0.02); }
            td { border: none; position: relative; padding-left: 50%; display: flex; justify-content: flex-end; align-items: center; text-align: right; min-height: 2.5rem; }
            td:before { position: absolute; left: 1rem; width: 45%; white-space: nowrap; text-align: left; font-weight: 600; color: var(--text-secondary); content: attr(data-label); font-size: 0.8rem; text-transform: uppercase; }
            .aliases-container { max-width: 100%; justify-content: flex-end; }
        }
        .spinner { border: 3px solid rgba(255, 255, 255, 0.1); width: 24px; height: 24px; border-radius: 50%; border-left-color: var(--accent-color); animation: spin 1s linear infinite; display: inline-block; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .loading-overlay { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 3rem; gap: 1rem; color: var(--text-secondary); }
    </style>
</head>
<body>
<div class="container">
    <header class="glass-panel">
        <div class="logo-section">
            <div class="logo-icon">
                <svg viewBox="0 0 24 24"><path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.02 1.62 4.2 1.23 1.37 2.95 2.19 4.79 2.45v3.91c-1.5-.07-2.97-.61-4.22-1.46-.71-.49-1.34-1.1-1.85-1.81v6.94c.03 2.17-.67 4.31-2.02 6.01-1.74 2.11-4.46 3.32-7.18 3.19-2.92-.09-5.74-1.63-7.29-4.14-1.64-2.58-1.92-5.91-.72-8.73 1.15-2.73 3.73-4.7 6.69-5.11v3.96c-1.57.17-3.03 1.12-3.73 2.53-.78 1.53-.61 3.49.44 4.88 1.07 1.48 2.96 2.22 4.78 1.83 1.45-.27 2.72-1.34 3.16-2.76.15-.55.22-1.12.21-1.7V0h.84z"/></svg>
            </div>
            <div class="logo-title">
                <h1>TikTok Streak Bot</h1>
                <p>Cổng Quản Trị Hệ Thống (Cloudflare Workers)</p>
            </div>
        </div>
        <div class="header-actions">
            <button class="btn btn-secondary" onclick="openApiKeyModal()">Khóa API</button>
            <button class="btn btn-primary" onclick="openAddModal()">Thêm Bạn Bè</button>
        </div>
    </header>
    <div class="glass-panel stats-grid">
        <div class="stat-card">
            <div class="stat-label">Tổng liên hệ</div>
            <div class="stat-value" id="stat-total">-</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Đang kích hoạt</div>
            <div class="stat-value success" id="stat-enabled">-</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Lượt gửi thành công</div>
            <div class="stat-value" id="stat-success-sent">-</div>
        </div>
    </div>
    <div class="glass-panel dashboard-body">
        <div class="panel-header">
            <div class="panel-title">Danh Sách Bạn Bè Chạy Streak</div>
            <button class="btn btn-secondary btn-icon" onclick="fetchContacts()">Tải Lại</button>
        </div>
        <div id="loading-state" class="loading-overlay">
            <div class="spinner"></div>
            <p>Đang tải danh sách bạn bè...</p>
        </div>
        <div id="empty-state" class="loading-overlay" style="display: none;">
            <p>Chưa có bạn bè nào trong danh sách streak.</p>
            <button class="btn btn-primary" onclick="openAddModal()">Thêm Ngay</button>
        </div>
        <div class="table-container" id="table-container" style="display: none;">
            <table>
                <thead>
                    <tr>
                        <th style="width: 30%;">Bạn bè</th>
                        <th style="width: 25%;">Biệt danh phụ</th>
                        <th style="width: 20%;">Trạng thái gửi cuối</th>
                        <th style="width: 12%; text-align: center;">Chạy bot</th>
                        <th style="width: 13%; text-align: center;">Hành động</th>
                    </tr>
                </thead>
                <tbody id="contacts-tbody"></tbody>
            </table>
        </div>
    </div>
</div>

<!-- Modal Config API -->
<div class="modal-overlay" id="api-key-modal">
    <div class="modal-card">
        <div class="modal-header">
            <div class="modal-title">Cấu Hình Khóa API</div>
            <button class="modal-close" onclick="closeModal('api-key-modal')">&times;</button>
        </div>
        <div class="form-group">
            <label for="input-api-url">Địa Chỉ API (Tự nhận diện)</label>
            <input type="text" id="input-api-url" class="form-input">
        </div>
        <div class="form-group">
            <label for="input-api-key">Khóa Bảo Mật (API Key)</label>
            <input type="password" id="input-api-key" class="form-input" placeholder="Nhập API_KEY bạn đặt trong script">
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" onclick="closeModal('api-key-modal')">Hủy</button>
            <button class="btn btn-primary" onclick="saveApiConfig()">Lưu Cấu Hình</button>
        </div>
    </div>
</div>

<!-- Add Contact Modal -->
<div class="modal-overlay" id="add-contact-modal">
    <div class="modal-card">
        <div class="modal-header">
            <div class="modal-title">Thêm Bạn Bè Mới</div>
            <button class="modal-close" onclick="closeModal('add-contact-modal')">&times;</button>
        </div>
        <form id="add-contact-form" onsubmit="handleAddContact(event)">
            <div class="form-group">
                <label for="add-username">Username TikTok (@)</label>
                <input type="text" id="add-username" class="form-input" required placeholder="Ví dụ: pnv.nguyen">
            </div>
            <div class="form-group">
                <label for="add-display-name">Tên Hiển Thị</label>
                <input type="text" id="add-display-name" class="form-input" placeholder="Ví dụ: Nguyễn Văn A">
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" onclick="closeModal('add-contact-modal')">Hủy</button>
                <button type="submit" class="btn btn-primary">Thêm Bạn</button>
            </div>
        </form>
    </div>
</div>

<!-- Edit Aliases Modal -->
<div class="modal-overlay" id="edit-aliases-modal">
    <div class="modal-card">
        <div class="modal-header">
            <div class="modal-title" id="alias-modal-title">Quản Lý Biệt Hiệu Phụ</div>
            <button class="modal-close" onclick="closeModal('edit-aliases-modal')">&times;</button>
        </div>
        <form id="edit-aliases-form" onsubmit="handleUpdateAliases(event)">
            <input type="hidden" id="alias-username">
            <div class="form-group">
                <label for="alias-input">Biệt Danh Phụ (Cách nhau bằng dấu phẩy)</label>
                <input type="text" id="alias-input" class="form-input" placeholder="Ví dụ: A mập, Bạn thân">
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" onclick="closeModal('edit-aliases-modal')">Hủy</button>
                <button type="submit" class="btn btn-primary">Cập Nhật</button>
            </div>
        </form>
    </div>
</div>

<div class="toast-container" id="toast-container"></div>

<script>
    let API_URL = '';
    let API_KEY = '';

    document.addEventListener("DOMContentLoaded", function() {
        API_URL = localStorage.getItem("TIKTOK_API_URL") || "";
        API_KEY = localStorage.getItem("TIKTOK_API_KEY") || "";

        if (!API_URL) {
            API_URL = window.location.origin + '/api';
            localStorage.setItem("TIKTOK_API_URL", API_URL);
        }

        document.getElementById("input-api-url").value = API_URL;
        document.getElementById("input-api-key").value = API_KEY;

        if (!API_KEY) {
            showToast("Vui lòng cấu hình API Key để kết nối.", "warning");
            openApiKeyModal();
        } else {
            fetchContacts();
        }
    });

    function showToast(message, type) {
        if (!type) type = 'success';
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = 'toast ' + type;
        const msgDiv = document.createElement('div');
        msgDiv.textContent = message;
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '&times;';
        closeBtn.style.cssText = 'background:none;border:none;color:rgba(255,255,255,0.4);margin-left:12px;cursor:pointer;font-size:1.1rem;';
        closeBtn.onclick = function() { this.parentElement.remove(); };
        toast.appendChild(msgDiv);
        toast.appendChild(closeBtn);
        container.appendChild(toast);
        setTimeout(function() { toast.classList.add('show'); }, 10);
        setTimeout(function() {
            toast.classList.remove('show');
            setTimeout(function() { toast.remove(); }, 300);
        }, 4000);
    }

    function openModal(id) { document.getElementById(id).classList.add("active"); }
    function closeModal(id) { document.getElementById(id).classList.remove("active"); }
    function openApiKeyModal() { openModal("api-key-modal"); }
    
    function saveApiConfig() {
        API_URL = document.getElementById("input-api-url").value.trim();
        API_KEY = document.getElementById("input-api-key").value.trim();
        localStorage.setItem("TIKTOK_API_URL", API_URL);
        localStorage.setItem("TIKTOK_API_KEY", API_KEY);
        closeModal("api-key-modal");
        showToast("Đã lưu cấu hình API.", "success");
        fetchContacts();
    }

    function openAddModal() {
        document.getElementById("add-contact-form").reset();
        openModal("add-contact-modal");
    }

    function openEditAliasesModal(username, currentAliases) {
        document.getElementById("alias-username").value = username;
        document.getElementById("alias-modal-title").innerText = "Biệt danh của @" + username;
        document.getElementById("alias-input").value = currentAliases.join(", ");
        openModal("edit-aliases-modal");
    }

    async function fetchContacts() {
        const loadingEl = document.getElementById("loading-state");
        const emptyEl = document.getElementById("empty-state");
        const tableContainerEl = document.getElementById("table-container");
        loadingEl.style.display = "flex"; emptyEl.style.display = "none"; tableContainerEl.style.display = "none";

        try {
            const response = await fetch(API_URL + "?action=get_contacts", {
                headers: { 'x-api-key': API_KEY }
            });
            if (response.status === 401) {
                showToast("Khóa API không chính xác.", "error");
                openApiKeyModal();
                return;
            }
            const contacts = await response.json();
            renderDashboard(contacts);
        } catch (error) {
            showToast("Lỗi: " + error.message, "error");
        } finally {
            loadingEl.style.display = "none";
        }
    }

    function renderDashboard(contacts) {
        const emptyEl = document.getElementById("empty-state");
        const tableContainerEl = document.getElementById("table-container");
        const tbody = document.getElementById("contacts-tbody");

        if (!contacts || contacts.length === 0) {
            emptyEl.style.display = "flex";
            updateStats(0, 0, 0);
            return;
        }

        tableContainerEl.style.display = "block";
        tbody.innerHTML = "";
        let total = contacts.length, enabledCount = 0, successSent = 0;

        contacts.forEach(c => {
            if (c.enabled) enabledCount++;
            successSent += Number(c.success_count || 0);

            let statusBadge = '<span class="badge badge-warning">Chưa chạy</span>';
            if (c.last_sent === 'success') {
                statusBadge = '<span class="badge badge-success">Thành công</span>';
            } else if (c.last_sent === 'failed') {
                statusBadge = '<span class="badge badge-error">Thất bại</span>';
            }

            let aliasesHtml = '<span style="font-style:italic;color:var(--text-secondary);">Không có</span>';
            if (c.aliases && c.aliases.length > 0) {
                aliasesHtml = '<div class="aliases-container">' + c.aliases.map(a => '<span class="alias-tag">' + escapeHtml(a) + '</span>').join('') + '</div>';
            }

            const uName = escapeHtml(c.display_name || c.username);
            const uHandle = escapeHtml(c.username);
            const aliasesJson = JSON.stringify(c.aliases || []).replace(/'/g, '&#39;');
            const checkedAttr = c.enabled ? 'checked' : '';

            const tr = document.createElement('tr');
            tr.innerHTML = '<td data-label="Bạn bè">' +
                '<div class="user-info">' +
                '<span class="user-name">' + uName + '</span>' +
                '<a href="https://www.tiktok.com/@' + uHandle + '" target="_blank" class="user-handle">@' + uHandle + '</a>' +
                '</div></td>' +
                '<td data-label="Biệt hiệu phụ">' + aliasesHtml + '</td>' +
                '<td data-label="Trạng thái">' +
                '<div>' + statusBadge + '</div>' +
                '<div style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px;">Thành công: ' + c.success_count + ' | Thất bại: ' + c.failure_count + '</div>' +
                '</td>' +
                '<td data-label="Chạy bot" style="text-align:center;">' +
                '<label class="switch">' +
                '<input type="checkbox" ' + checkedAttr + ' onchange="toggleContact(\'' + uHandle + '\', this.checked)">' +
                '<span class="slider"></span>' +
                '</label></td>' +
                '<td data-label="Hành động" style="text-align:center;">' +
                '<div class="action-cell" style="justify-content:flex-end;">' +
                '<button class="btn btn-secondary btn-icon" onclick="openEditAliasesModal(\'' + uHandle + '\', ' + aliasesJson + ')">Sửa</button>' +
                '<button class="btn btn-danger btn-icon" onclick="deleteContact(\'' + uHandle + '\')">Xóa</button>' +
                '</div></td>';
            tbody.appendChild(tr);
        });
        updateStats(total, enabledCount, successSent);
    }

    function updateStats(total, enabled, success) {
        document.getElementById("stat-total").innerText = total;
        document.getElementById("stat-enabled").innerText = enabled;
        document.getElementById("stat-success-sent").innerText = success;
    }

    async function toggleContact(username, isEnabled) {
        try {
            await fetch(API_URL + "?action=toggle_contact&username=" + encodeURIComponent(username) + "&enabled=" + (isEnabled ? 1 : 0), {
                headers: { 'x-api-key': API_KEY }
            });
            showToast("Đã cập nhật trạng thái.", "success");
            fetchContacts();
        } catch (error) {
            showToast("Lỗi cập nhật.", "error");
        }
    }

    async function handleAddContact(event) {
        event.preventDefault();
        const username = document.getElementById("add-username").value.trim();
        const displayName = document.getElementById("add-display-name").value.trim();

        try {
            await fetch(API_URL + "?action=add_contact&username=" + encodeURIComponent(username) + "&display_name=" + encodeURIComponent(displayName), {
                headers: { 'x-api-key': API_KEY }
            });
            showToast("Thêm thành công.", "success");
            closeModal("add-contact-modal");
            fetchContacts();
        } catch (error) {
            showToast("Lỗi: " + error.message, "error");
        }
    }

    async function handleUpdateAliases(event) {
        event.preventDefault();
        const username = document.getElementById("alias-username").value;
        const aliases = document.getElementById("alias-input").value;

        try {
            await fetch(API_URL + "?action=update_aliases&username=" + encodeURIComponent(username) + "&aliases=" + encodeURIComponent(aliases), {
                headers: { 'x-api-key': API_KEY }
            });
            showToast("Cập nhật thành công.", "success");
            closeModal("edit-aliases-modal");
            fetchContacts();
        } catch (error) {
            showToast("Lỗi.", "error");
        }
    }

    async function deleteContact(username) {
        if (!confirm("Xóa?")) return;
        try {
            await fetch(API_URL + "?action=delete_contact&username=" + encodeURIComponent(username), {
                headers: { 'x-api-key': API_KEY }
            });
            showToast("Đã xóa.", "success");
            fetchContacts();
        } catch (error) {
            showToast("Lỗi.", "error");
        }
    }

    function escapeHtml(text) {
        if (!text) return "";
        return text.toString().replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }
</script>
</body>
</html>`;
}
