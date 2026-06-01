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

          case "update_contact": {
            const username = url.searchParams.get("username");
            const displayName = url.searchParams.get("display_name") || "";
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

            await env.DB.prepare("UPDATE tiktok_contacts SET display_name = ?1, aliases = ?2 WHERE username = ?3")
              .bind(displayName || username, aliasesJson, username)
              .run();

            return new Response(JSON.stringify({ status: "success", message: "Cập nhật thông tin bạn bè thành công." }), {
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
            --bg-color: #080c16;
            --panel-bg: rgba(17, 25, 40, 0.65);
            --panel-border: rgba(255, 255, 255, 0.08);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-gradient: linear-gradient(135deg, #a78bfa, #3b82f6);
            --accent-color: #a78bfa;
            --success-color: #10b981;
            --error-color: #f87171;
            --warning-color: #fbbf24;
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
            width: 44px; height: 44px;
            background: var(--accent-gradient);
            border-radius: 12px;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4);
        }
        .logo-icon svg { width: 26px; height: 26px; fill: white; }
        .logo-title h1 {
            font-size: 1.5rem; font-weight: 700;
            background: linear-gradient(to right, #ffffff, #d1d5db);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .logo-title p { font-size: 0.8rem; color: var(--text-secondary); }
        .header-actions { display: flex; gap: 0.75rem; }
        .btn {
            font-family: var(--font-family);
            display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem;
            padding: 0.6rem 1.2rem; border-radius: 8px;
            font-weight: 500; font-size: 0.9rem; cursor: pointer;
            transition: all var(--transition-speed) ease; border: none; text-decoration: none;
        }
        .btn:active { transform: scale(0.97); }
        .btn-primary { background: var(--accent-gradient); color: white; box-shadow: 0 4px 12px rgba(139, 92, 246, 0.2); }
        .btn-primary:hover { opacity: 0.9; transform: translateY(-1px); box-shadow: 0 6px 15px rgba(139, 92, 246, 0.3); }
        .btn-secondary { background: rgba(255, 255, 255, 0.05); color: var(--text-primary); border: 1px solid var(--panel-border); }
        .btn-secondary:hover { background: rgba(255, 255, 255, 0.12); transform: translateY(-1px); }
        .btn-danger { background: rgba(239, 68, 68, 0.12); color: var(--error-color); border: 1px solid rgba(239, 68, 68, 0.2); }
        .btn-danger:hover { background: rgba(239, 68, 68, 0.22); transform: translateY(-1px); }
        
        /* Stats Styling */
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }
        .stat-card { display: flex; align-items: center; gap: 1.25rem; transition: all var(--transition-speed) ease; }
        .stat-card:hover { transform: translateY(-4px) scale(1.02); border-color: rgba(139, 92, 246, 0.25); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }
        .stat-icon {
            width: 48px; height: 48px; border-radius: 12px;
            background: rgba(167, 139, 250, 0.08);
            display: flex; align-items: center; justify-content: center;
            color: var(--accent-color); border: 1px solid rgba(167, 139, 250, 0.15);
        }
        .stat-icon svg { width: 22px; height: 22px; fill: currentColor; }
        .stat-content { display: flex; flex-direction: column; gap: 0.15rem; }
        .stat-label { font-size: 0.8rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; }
        .stat-value { font-size: 1.7rem; font-weight: 700; color: white; }
        .stat-value.success { color: var(--success-color); }
        
        /* Dashboard Control Section */
        .dashboard-body { overflow: hidden; display: flex; flex-direction: column; gap: 1rem; }
        .panel-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; margin-bottom: 0.5rem; }
        .panel-title { font-size: 1.15rem; font-weight: 600; }
        
        .controls-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }
        .search-box { position: relative; max-width: 320px; width: 100%; }
        .search-input {
            width: 100%; padding: 0.6rem 1rem 0.6rem 2.5rem; border-radius: 8px;
            background: rgba(255, 255, 255, 0.04); border: 1px solid var(--panel-border);
            color: white; font-family: var(--font-family); font-size: 0.9rem; outline: none;
            transition: all var(--transition-speed) ease;
        }
        .search-input:focus { border-color: var(--accent-color); background: rgba(255, 255, 255, 0.08); box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.15); }
        .search-icon { position: absolute; left: 0.75rem; top: 50%; transform: translateY(-50%); color: var(--text-secondary); width: 16px; height: 16px; }
        .search-icon svg { width: 100%; height: 100%; fill: currentColor; }
        
        .filter-tabs { display: flex; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--panel-border); padding: 0.25rem; border-radius: 10px; gap: 0.25rem; }
        .filter-tab {
            padding: 0.45rem 1rem; border-radius: 8px; font-size: 0.85rem; font-weight: 500;
            color: var(--text-secondary); cursor: pointer; transition: all var(--transition-speed) ease;
            border: none; background: transparent; font-family: var(--font-family);
        }
        .filter-tab.active { background: var(--accent-gradient); color: white; box-shadow: 0 2px 8px rgba(139, 92, 246, 0.25); }
        .filter-tab:hover:not(.active) { color: var(--text-primary); background: rgba(255, 255, 255, 0.05); }

        /* Table Styling */
        .table-container { width: 100%; overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.95rem; }
        th { padding: 1rem; font-weight: 600; color: var(--text-secondary); border-bottom: 1px solid var(--panel-border); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
        td { padding: 1rem; border-bottom: 1px solid rgba(255, 255, 255, 0.03); vertical-align: middle; }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background-color: rgba(255, 255, 255, 0.012); }
        
        .user-info { display: flex; align-items: center; gap: 0.75rem; }
        .user-avatar-placeholder {
            width: 36px; height: 36px; border-radius: 50%;
            background: rgba(139, 92, 246, 0.1); border: 1px solid rgba(139, 92, 246, 0.2);
            display: flex; align-items: center; justify-content: center; color: var(--accent-color);
        }
        .user-avatar-placeholder svg { width: 18px; height: 18px; fill: currentColor; }
        .user-details { display: flex; flex-direction: column; gap: 0.15rem; }
        .user-name { font-weight: 600; color: white; }
        .user-handle { font-size: 0.8rem; color: var(--text-secondary); text-decoration: none; display: inline-flex; align-items: center; gap: 0.25rem; }
        .user-handle:hover { color: var(--accent-color); }
        .user-handle svg { width: 12px; height: 12px; fill: currentColor; }
        
        /* Switch switch toggler */
        .switch { position: relative; display: inline-block; width: 44px; height: 24px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(255, 255, 255, 0.08); transition: .3s; border-radius: 24px; border: 1px solid var(--panel-border); }
        .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: white; transition: .3s; border-radius: 50%; }
        input:checked + .slider { background: var(--accent-gradient); }
        input:checked + .slider:before { transform: translateX(20px); }
        
        /* Badges */
        .badge { display: inline-flex; align-items: center; padding: 0.25rem 0.6rem; border-radius: 50px; font-size: 0.75rem; font-weight: 600; }
        .badge-success { background-color: rgba(16, 185, 129, 0.12); color: var(--success-color); border: 1px solid rgba(16, 185, 129, 0.2); }
        .badge-error { background-color: rgba(239, 68, 68, 0.12); color: var(--error-color); border: 1px solid rgba(239, 68, 68, 0.2); }
        .badge-warning { background-color: rgba(245, 158, 11, 0.12); color: var(--warning-color); border: 1px solid rgba(245, 158, 11, 0.2); }
        
        .aliases-container { display: flex; flex-wrap: wrap; gap: 0.25rem; max-width: 250px; }
        .alias-tag { background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 6px; padding: 0.15rem 0.45rem; font-size: 0.75rem; color: var(--text-secondary); }
        
        /* Action buttons with tooltips */
        .action-cell { display: flex; gap: 0.5rem; justify-content: center; }
        .btn-icon-only {
            padding: 0.5rem; border-radius: 8px; border: 1px solid var(--panel-border);
            background: rgba(255, 255, 255, 0.04); color: var(--text-secondary);
            display: inline-flex; align-items: center; justify-content: center;
            cursor: pointer; transition: all var(--transition-speed) ease;
        }
        .btn-icon-only:hover { color: white; background: rgba(255, 255, 255, 0.1); transform: translateY(-1px); }
        .btn-icon-only.edit:hover { border-color: rgba(139, 92, 246, 0.3); color: var(--accent-color); }
        .btn-icon-only.delete:hover { border-color: rgba(239, 68, 68, 0.3); color: var(--error-color); background: rgba(239, 68, 68, 0.05); }
        .btn-icon-only svg { width: 16px; height: 16px; fill: currentColor; }
        
        /* Tooltip Container */
        .tooltip { position: relative; }
        .tooltip:before {
            content: attr(data-tooltip); position: absolute; bottom: 125%; left: 50%; transform: translateX(-50%);
            background: #0f172a; border: 1px solid var(--panel-border); color: white;
            padding: 0.35rem 0.6rem; border-radius: 6px; font-size: 0.75rem; white-space: nowrap;
            opacity: 0; pointer-events: none; transition: all var(--transition-speed) ease;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5); z-index: 100;
        }
        .tooltip:hover:before { opacity: 1; bottom: 135%; }

        /* Modals & Inputs */
        .modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0, 0, 0, 0.65); backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; opacity: 0; pointer-events: none; transition: all 0.3s ease; z-index: 1000; }
        .modal-overlay.active { opacity: 1; pointer-events: auto; }
        .modal-card { background: rgba(11, 15, 26, 0.96); border: 1px solid var(--panel-border); border-radius: 16px; width: 90%; max-width: 450px; padding: 1.5rem; box-shadow: 0 20px 40px rgba(0,0,0,0.6); transform: scale(0.95); transition: all 0.3s ease; }
        .modal-overlay.active .modal-card { transform: scale(1); }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; }
        .modal-title { font-size: 1.15rem; font-weight: 600; }
        .modal-close { background: none; border: none; color: var(--text-secondary); font-size: 1.5rem; cursor: pointer; line-height: 1; outline: none; }
        .modal-close:hover { color: white; }
        .form-group { display: flex; flex-direction: column; gap: 0.4rem; margin-bottom: 1.2rem; }
        .form-group label { font-size: 0.85rem; font-weight: 500; color: var(--text-secondary); }
        .form-input { background-color: rgba(255, 255, 255, 0.03); border: 1px solid var(--panel-border); border-radius: 8px; padding: 0.7rem; color: white; font-family: var(--font-family); font-size: 0.9rem; outline: none; transition: all var(--transition-speed) ease; }
        .form-input:focus { border-color: var(--accent-color); background-color: rgba(255, 255, 255, 0.06); box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.15); }
        .form-help { font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.15rem; }
        .modal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.5rem; }
        
        /* Toast Notification */
        .toast-container { position: fixed; bottom: 2rem; right: 2rem; display: flex; flex-direction: column; gap: 0.5rem; z-index: 2000; max-width: 350px; }
        .toast { background: rgba(15, 23, 42, 0.92); backdrop-filter: blur(8px); border-left: 4px solid var(--accent-color); border-top: 1px solid var(--panel-border); border-right: 1px solid var(--panel-border); border-bottom: 1px solid var(--panel-border); border-radius: 0 8px 8px 0; padding: 0.9rem 1.2rem; color: white; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 10px 25px rgba(0,0,0,0.5); transform: translateY(100px); opacity: 0; transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
        .toast.show { transform: translateY(0); opacity: 1; }
        .toast.success { border-left-color: var(--success-color); }
        .toast.error { border-left-color: var(--error-color); }
        .toast.warning { border-left-color: var(--warning-color); }
        .toast-content { font-size: 0.85rem; font-weight: 500; }
        
        /* Mobile Responsiveness */
        @media (max-width: 768px) {
            header.glass-panel { flex-direction: column; align-items: flex-start; }
            .header-actions { width: 100%; justify-content: space-between; }
            .controls-row { flex-direction: column; align-items: stretch; }
            .search-box { max-width: 100%; }
            .filter-tabs { width: 100%; justify-content: space-around; }
            table, thead, tbody, th, td, tr { display: block; }
            thead tr { position: absolute; top: -9999px; left: -9999px; }
            tr { border: 1px solid var(--panel-border); border-radius: 12px; margin-bottom: 1rem; padding: 0.5rem; background-color: rgba(255, 255, 255, 0.015); }
            td { border: none; position: relative; padding-left: 50%; display: flex; justify-content: flex-end; align-items: center; text-align: right; min-height: 2.75rem; }
            td:before { position: absolute; left: 1rem; width: 45%; white-space: nowrap; text-align: left; font-weight: 600; color: var(--text-secondary); content: attr(data-label); font-size: 0.8rem; text-transform: uppercase; }
            .aliases-container { max-width: 100%; justify-content: flex-end; }
            .action-cell { justify-content: flex-end; }
        }
        .spinner { border: 3px solid rgba(255, 255, 255, 0.1); width: 24px; height: 24px; border-radius: 50%; border-left-color: var(--accent-color); animation: spin 1s linear infinite; display: inline-block; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .loading-overlay { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 4rem; gap: 1rem; color: var(--text-secondary); }
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
            <button class="btn btn-secondary" onclick="openApiKeyModal()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
                Khóa API
            </button>
            <button class="btn btn-primary" onclick="openAddModal()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2m8-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM20 8v6m3-3h-6"/></svg>
                Thêm Bạn Bè
            </button>
        </div>
    </header>
    
    <div class="glass-panel stats-grid">
        <div class="stat-card">
            <div class="stat-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 7a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            </div>
            <div class="stat-content">
                <div class="stat-label">Tổng liên hệ</div>
                <div class="stat-value" id="stat-total">-</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="color: var(--success-color); background: rgba(16, 185, 129, 0.08); border-color: rgba(16, 185, 129, 0.15)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4L12 14.01l-3-3"/></svg>
            </div>
            <div class="stat-content">
                <div class="stat-label">Đang kích hoạt</div>
                <div class="stat-value success" id="stat-enabled">-</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="color: var(--warning-color); background: rgba(245, 158, 11, 0.08); border-color: rgba(245, 158, 11, 0.15)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
            </div>
            <div class="stat-content">
                <div class="stat-label">Lượt gửi thành công</div>
                <div class="stat-value" id="stat-success-sent">-</div>
            </div>
        </div>
    </div>
    
    <div class="glass-panel dashboard-body">
        <div class="panel-header">
            <div class="panel-title">Danh Sách Bạn Bè Chạy Streak</div>
            <button class="btn btn-secondary btn-icon" onclick="fetchContacts()" style="padding: 0.5rem 0.8rem;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
                Tải Lại
            </button>
        </div>
        
        <div class="controls-row">
            <div class="search-box">
                <div class="search-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                </div>
                <input type="text" id="search-input" class="search-input" placeholder="Tìm tên, username, biệt danh..." oninput="filterAndRenderContacts()">
            </div>
            <div class="filter-tabs">
                <button class="filter-tab active" data-tab="all" onclick="changeFilterTab('all')">Tất cả</button>
                <button class="filter-tab" data-tab="active" onclick="changeFilterTab('active')">Hoạt động</button>
                <button class="filter-tab" data-tab="success" onclick="changeFilterTab('success')">Thành công</button>
                <button class="filter-tab" data-tab="failed" onclick="changeFilterTab('failed')">Thất bại</button>
            </div>
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
                        <th style="width: 32%;">Bạn bè</th>
                        <th style="width: 25%;">Biệt hiệu phụ</th>
                        <th style="width: 21%;">Trạng thái gửi cuối</th>
                        <th style="width: 10%; text-align: center;">Chạy bot</th>
                        <th style="width: 12%; text-align: center;">Hành động</th>
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

<!-- Edit Contact Modal (Unified Edit Name + Aliases) -->
<div class="modal-overlay" id="edit-contact-modal">
    <div class="modal-card">
        <div class="modal-header">
            <div class="modal-title" id="edit-contact-title">Chỉnh Sửa Bạn Bè</div>
            <button class="modal-close" onclick="closeModal('edit-contact-modal')">&times;</button>
        </div>
        <form id="edit-contact-form" onsubmit="handleUpdateContact(event)">
            <input type="hidden" id="edit-username">
            <div class="form-group">
                <label for="edit-display-name-input">Tên Hiển Thị</label>
                <input type="text" id="edit-display-name-input" class="form-input" required placeholder="Ví dụ: Nguyễn Văn A">
            </div>
            <div class="form-group">
                <label for="edit-aliases-input">Biệt Danh Phụ (Cách nhau bằng dấu phẩy)</label>
                <input type="text" id="edit-aliases-input" class="form-input" placeholder="Ví dụ: A mập, Bạn thân">
                <div class="form-help">Biệt danh phụ giúp bot quét nhanh cuộc hội thoại trong thanh sidebar.</div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" onclick="closeModal('edit-contact-modal')">Hủy</button>
                <button type="submit" class="btn btn-primary">Lưu Thay Đổi</button>
            </div>
        </form>
    </div>
</div>

<div class="toast-container" id="toast-container"></div>

<script>
    let API_URL = '';
    let API_KEY = '';
    let allContacts = [];

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
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'toast-content';
        contentDiv.textContent = message;
        
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '&times;';
        closeBtn.style.cssText = 'background:none;border:none;color:rgba(255,255,255,0.4);margin-left:12px;cursor:pointer;font-size:1.1rem;';
        closeBtn.onclick = function() { this.parentElement.remove(); };
        
        toast.appendChild(contentDiv);
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

    function openEditContactModal(username, displayName, currentAliases) {
        document.getElementById("edit-username").value = username;
        document.getElementById("edit-contact-title").innerText = "Chỉnh sửa bạn bè @" + username;
        document.getElementById("edit-display-name-input").value = displayName || username;
        document.getElementById("edit-aliases-input").value = currentAliases.join(", ");
        openModal("edit-contact-modal");
    }

    function changeFilterTab(tabName) {
        document.querySelectorAll(".filter-tab").forEach(tab => {
            if (tab.dataset.tab === tabName) {
                tab.classList.add("active");
            } else {
                tab.classList.remove("active");
            }
        });
        filterAndRenderContacts();
    }

    async function fetchContacts() {
        var loadingEl = document.getElementById("loading-state");
        var emptyEl = document.getElementById("empty-state");
        var tableContainerEl = document.getElementById("table-container");
        loadingEl.style.display = "flex"; emptyEl.style.display = "none"; tableContainerEl.style.display = "none";

        try {
            console.log('[Dashboard] Fetching contacts from:', API_URL + '?action=get_contacts');
            var response = await fetch(API_URL + "?action=get_contacts", {
                headers: { 'x-api-key': API_KEY }
            });
            console.log('[Dashboard] Response status:', response.status);
            if (response.status === 401) {
                loadingEl.style.display = "none";
                showToast("Khóa API không chính xác. Vui lòng kiểm tra lại.", "error");
                openApiKeyModal();
                return;
            }
            if (!response.ok) {
                loadingEl.style.display = "none";
                showToast("Lỗi máy chủ: HTTP " + response.status, "error");
                return;
            }
            allContacts = await response.json();
            console.log('[Dashboard] Loaded contacts:', allContacts.length);
            filterAndRenderContacts();
        } catch (error) {
            console.error('[Dashboard] Fetch error:', error);
            showToast("Lỗi kết nối: " + error.message, "error");
        } finally {
            loadingEl.style.display = "none";
        }
    }

    function filterAndRenderContacts() {
        const query = document.getElementById("search-input").value.toLowerCase().trim();
        const activeTab = document.querySelector(".filter-tab.active").dataset.tab;
        
        let filtered = allContacts;
        
        // 1. Lọc theo thanh tìm kiếm
        if (query) {
            filtered = filtered.filter(c => {
                const username = (c.username || "").toLowerCase();
                const displayName = (c.display_name || "").toLowerCase();
                const aliases = c.aliases || [];
                return username.includes(query) || 
                       displayName.includes(query) || 
                       aliases.some(a => a.toLowerCase().includes(query));
            });
        }
        
        // 2. Lọc theo tab trạng thái
        if (activeTab === "active") {
            filtered = filtered.filter(c => c.enabled);
        } else if (activeTab === "success") {
            filtered = filtered.filter(c => c.last_sent === "success");
        } else if (activeTab === "failed") {
            filtered = filtered.filter(c => c.last_sent === "failed");
        }
        
        renderContactsList(filtered);
    }

    function renderContactsList(contacts) {
        const emptyEl = document.getElementById("empty-state");
        const tableContainerEl = document.getElementById("table-container");
        const tbody = document.getElementById("contacts-tbody");

        // Cập nhật thống kê nhanh từ danh sách gốc (allContacts)
        let total = allContacts.length;
        let enabledCount = 0;
        let successSent = 0;
        allContacts.forEach(c => {
            if (c.enabled) enabledCount++;
            successSent += Number(c.success_count || 0);
        });
        updateStats(total, enabledCount, successSent);

        if (!contacts || contacts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-secondary);padding:3rem;">Không tìm thấy bạn bè nào khớp bộ lọc.</td></tr>';
            tableContainerEl.style.display = "block";
            return;
        }

        tableContainerEl.style.display = "block";
        tbody.innerHTML = "";

        contacts.forEach(c => {
            let statusBadge = '<span class="badge badge-warning">Chưa chạy</span>';
            if (c.last_sent === 'success') {
                statusBadge = '<span class="badge badge-success">Thành công</span>';
            } else if (c.last_sent === 'failed') {
                statusBadge = '<span class="badge badge-error">Thất bại</span>';
            }

            let aliasesHtml = '<span style="font-style:italic;color:var(--text-secondary);font-size:0.85rem;">Không có</span>';
            if (c.aliases && c.aliases.length > 0) {
                aliasesHtml = '<div class="aliases-container">' + c.aliases.map(a => '<span class="alias-tag">' + escapeHtml(a) + '</span>').join('') + '</div>';
            }

            const uName = escapeHtml(c.display_name || c.username);
            const uHandle = escapeHtml(c.username);
            const aliasesJson = JSON.stringify(c.aliases || []).replace(/'/g, '&#39;');
            const checkedAttr = c.enabled ? 'checked' : '';

            const tr = document.createElement('tr');
            
            // Xây dựng dòng HTML với cấu trúc chi tiết và biểu tượng SVG
            var cellsHtml = '<td data-label="Ban be">' +
                '<div class="user-info">' +
                '  <div class="user-avatar-placeholder">' +
                '    <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/></svg>' +
                '  </div>' +
                '  <div class="user-details">' +
                '    <span class="user-name">' + uName + '</span>' +
                '    <a href="https://www.tiktok.com/@' + uHandle + '" target="_blank" class="user-handle">@' + uHandle + ' ' +
                '      <svg viewBox="0 0 24 24"><path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/></svg>' +
                '    </a>' +
                '  </div>' +
                '</div></td>' +
                '<td data-label="Biệt hiệu phụ">' + aliasesHtml + '</td>' +
                '<td data-label="Trạng thái">' +
                '  <div>' + statusBadge + '</div>' +
                '  <div style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px;">Thành công: ' + c.success_count + ' | Thất bại: ' + c.failure_count + '</div>' +
                '</td>' +
                '<td data-label="Chạy bot" style="text-align:center;">' +
                '  <label class="switch">' +
                '    <input type="checkbox" ' + checkedAttr + ' onchange="toggleContact(\'' + uHandle + '\', this.checked)">' +
                '    <span class="slider"></span>' +
                '  </label></td>' +
                '<td data-label="Hành động" style="text-align:center;">' +
                '  <div class="action-cell">' +
                '    <button class="btn-icon-only edit tooltip" data-tooltip="Chỉnh sửa thông tin" onclick="openEditContactModal(\'' + uHandle + '\', \'' + uName.replace(/'/g, '\\\'') + '\', ' + aliasesJson.replace(/"/g, '&quot;') + ')">' +
                '      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>' +
                '    </button>' +
                '    <button class="btn-icon-only delete tooltip" data-tooltip="Xóa bạn bè" onclick="deleteContact(\'' + uHandle + '\')">' +
                '      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>' +
                '    </button>' +
                '  </div></td>';
                
            tr.innerHTML = cellsHtml;
            tbody.appendChild(tr);
        });
    }

    function updateStats(total, enabled, success) {
        document.getElementById("stat-total").innerText = total;
        document.getElementById("stat-enabled").innerText = enabled;
        document.getElementById("stat-success-sent").innerText = success;
    }

    async function toggleContact(username, isEnabled) {
        try {
            var res = await fetch(API_URL + "?action=toggle_contact&username=" + encodeURIComponent(username) + "&enabled=" + (isEnabled ? 1 : 0), {
                headers: { 'x-api-key': API_KEY }
            });
            if (res.ok) {
                showToast("Đã cập nhật trạng thái hoạt động.", "success");
                // Cập nhật trạng thái trong bộ nhớ và vẽ lại
                const contact = allContacts.find(c => c.username === username);
                if (contact) contact.enabled = isEnabled;
                filterAndRenderContacts();
            } else {
                showToast("Lỗi cập nhật máy chủ.", "error");
            }
        } catch (error) {
            showToast("Lỗi kết nối.", "error");
        }
    }

    async function handleAddContact(event) {
        event.preventDefault();
        const username = document.getElementById("add-username").value.trim();
        const displayName = document.getElementById("add-display-name").value.trim();

        try {
            const res = await fetch(API_URL + "?action=add_contact&username=" + encodeURIComponent(username) + "&display_name=" + encodeURIComponent(displayName), {
                headers: { 'x-api-key': API_KEY }
            });
            const data = await res.json();
            if (res.ok && data.status === "success") {
                showToast("Thêm bạn bè thành công.", "success");
                closeModal("add-contact-modal");
                fetchContacts();
            } else {
                showToast(data.message || "Lỗi khi thêm bạn bè.", "error");
            }
        } catch (error) {
            showToast("Lỗi: " + error.message, "error");
        }
    }

    async function handleUpdateContact(event) {
        event.preventDefault();
        const username = document.getElementById("edit-username").value;
        const displayName = document.getElementById("edit-display-name-input").value.trim();
        const aliases = document.getElementById("edit-aliases-input").value.trim();

        try {
            const res = await fetch(API_URL + "?action=update_contact&username=" + encodeURIComponent(username) + "&display_name=" + encodeURIComponent(displayName) + "&aliases=" + encodeURIComponent(aliases), {
                headers: { 'x-api-key': API_KEY }
            });
            const data = await res.json();
            if (res.ok && data.status === "success") {
                showToast("Đã cập nhật thông tin bạn bè.", "success");
                closeModal("edit-contact-modal");
                fetchContacts();
            } else {
                showToast(data.message || "Lỗi cập nhật.", "error");
            }
        } catch (error) {
            showToast("Lỗi: " + error.message, "error");
        }
    }

    async function deleteContact(username) {
        if (!confirm("Bạn có chắc chắn muốn xóa @" + username + " khỏi danh sách chạy streak?")) return;
        try {
            const res = await fetch(API_URL + "?action=delete_contact&username=" + encodeURIComponent(username), {
                headers: { 'x-api-key': API_KEY }
            });
            if (res.ok) {
                showToast("Đã xóa liên hệ khỏi danh sách.", "success");
                allContacts = allContacts.filter(c => c.username !== username);
                filterAndRenderContacts();
            } else {
                showToast("Lỗi máy chủ.", "error");
            }
        } catch (error) {
            showToast("Lỗi kết nối.", "error");
        }
    }

    function escapeHtml(text) {
        if (!text) return "";
        var s = text.toString();
        var out = '';
        for (var i = 0; i < s.length; i++) {
            var ch = s.charAt(i);
            if (ch === '&') out += '&amp;';
            else if (ch === String.fromCharCode(60)) out += '&lt;';
            else if (ch === String.fromCharCode(62)) out += '&gt;';
            else if (ch === '"') out += '&quot;';
            else if (ch === "'") out += '&#039;';
            else out += ch;
        }
        return out;
    }
</script>
</body>
</html>`;
}
