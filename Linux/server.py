import html
import http.server
import io
import json
import os
import re
import shutil
import socketserver
import urllib.parse
from http import HTTPStatus

PORT = 1711
AUTO_RELOAD_MS = 3000  # Auto-refresh interval (3 seconds)
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")


def natural_key(text):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", text)]


class GalleryHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        parsed = urllib.parse.urlsplit(path)
        req_path = parsed.path
        if (req_path == "/solarBot" or req_path.startswith("/solarBot/")) and not os.path.exists(
            os.path.join(self.directory, "solarBot")
        ):
            req_path = req_path[len("/solarBot") :] or "/"
            path = urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, req_path, parsed.query, parsed.fragment)
            )
        return super().translate_path(path)

    def do_POST(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path != "/__delete_folder__":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return

        content_len = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            data = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return

        target_url_path = data.get("path", "")
        root_dir = os.path.abspath(self.directory)
        target_dir = os.path.abspath(self.translate_path(target_url_path))

        # Safety check: never delete the root directory or anything outside it
        if target_dir == root_dir or not target_dir.startswith(root_dir + os.sep):
            self.send_error(HTTPStatus.FORBIDDEN, "Cannot delete root folder")
            return

        if not os.path.isdir(target_dir):
            self.send_error(HTTPStatus.NOT_FOUND, "Folder not found")
            return

        try:
            shutil.rmtree(target_dir)
        except OSError as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Delete failed: {e}")
            return

        resp = json.dumps({"ok": True}).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def list_directory(self, path):
        try:
            entries = os.listdir(path)
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "Cannot list directory")
            return None

        dirs, images, other_files = [], [], []
        for name in entries:
            full_path = os.path.join(path, name)
            if os.path.isdir(full_path):
                dirs.append(name)
            elif name.lower().endswith(IMG_EXTS):
                images.append(name)
            else:
                other_files.append(name)

        dirs.sort(key=natural_key)
        images.sort(key=natural_key)
        other_files.sort(key=natural_key)

        rel_path = urllib.parse.unquote(self.path)
        title = html.escape(f"Index of {rel_path}")

        nav_links = []
        if rel_path != "/":
            nav_links.append('<a class="chip dir" href="../">⬆ .. (Back)</a>')
        for d in dirs:
            href = urllib.parse.quote(d) + "/"
            nav_links.append(f'<a class="chip dir" href="{href}">📁 {html.escape(d)}/</a>')
        for f in other_files:
            href = urllib.parse.quote(f)
            nav_links.append(f'<a class="chip file" href="{href}">📄 {html.escape(f)}</a>')

        delete_btn_html = (
            '<button class="danger" onclick="deleteFolder()">🗑️ Delete Folder</button>'
            if rel_path != "/"
            else ""
        )

        img_data = json.dumps(
            [{"name": name, "url": urllib.parse.quote(name)} for name in images]
        ).replace("</", "<\\/")

        page = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #121212; color: #eee; font-family: monospace; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
  header {{ background: #1e1e1e; padding: 8px 14px; border-bottom: 1px solid #333; flex-shrink: 0; }}
  .topbar {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 6px; }}
  .path {{ font-size: 14px; color: #8ab4f8; }}
  .links {{ display: flex; flex-wrap: wrap; gap: 6px; max-height: 20vh; overflow-y: auto; }}
  .chip {{ text-decoration: none; padding: 4px 9px; border-radius: 4px; font-size: 13px; }}
  .dir {{ background: #263238; color: #80cbc4; border: 1px solid #37474f; }}
  .dir:hover {{ background: #37474f; }}
  .file {{ background: #222; color: #bbb; border: 1px solid #333; }}
  .file:hover {{ background: #333; }}

  #viewer {{ flex: 1; min-height: 0; display: none; flex-direction: column; align-items: center; justify-content: space-between; padding: 8px 10px 6px; }}
  .main-stage {{ flex: 1; min-height: 0; width: 100%; display: flex; align-items: center; justify-content: center; }}
  #preview {{ max-width: 96vw; max-height: 100%; object-fit: contain; border: 1px solid #333; background: #000; }}

  .controls {{ margin: 6px 0; display: flex; align-items: center; gap: 14px; font-size: 14px; flex-shrink: 0; }}
  button {{ background: #2a2a2a; color: #fff; border: 1px solid #555; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-family: monospace; }}
  button:hover {{ background: #3d3d3d; }}
  button.danger {{ background: #7f1d1d; border-color: #ef4444; color: #fecaca; padding: 4px 10px; font-size: 12px; }}
  button.danger:hover {{ background: #991b1b; }}
  #info {{ color: #ffd54f; }}

  /* Bottom Thumbnail Filmstrip */
  #thumb-strip {{
    width: 100%;
    height: 76px;
    background: #181818;
    border-top: 1px solid #333;
    padding: 6px 8px;
    display: flex;
    align-items: center;
    gap: 6px;
    overflow-x: auto;
    overflow-y: hidden;
    flex-shrink: 0;
    scrollbar-width: thin;
    scrollbar-color: #555 #181818;
  }}
  .thumb-item {{
    position: relative;
    height: 58px;
    min-width: 84px;
    max-width: 84px;
    border: 2px solid #333;
    border-radius: 4px;
    overflow: hidden;
    cursor: pointer;
    background: #000;
    flex-shrink: 0;
    opacity: 0.65;
    transition: opacity 0.12s, border-color 0.12s;
  }}
  .thumb-item:hover {{ opacity: 0.95; border-color: #888; }}
  .thumb-item.active {{ opacity: 1; border-color: #ffd54f; box-shadow: 0 0 6px rgba(255, 213, 79, 0.5); }}
  .thumb-item img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .thumb-num {{
    position: absolute;
    bottom: 1px;
    right: 3px;
    background: rgba(0, 0, 0, 0.75);
    color: #fff;
    font-size: 10px;
    padding: 0 3px;
    border-radius: 2px;
    pointer-events: none;
  }}
</style>
</head>
<body>
  <header>
    <div class="topbar">
      <div class="path">{title}</div>
      {delete_btn_html}
    </div>
    <div class="links">{''.join(nav_links)}</div>
  </header>
  <div id="viewer">
    <div class="main-stage">
      <img id="preview" src="" alt="">
    </div>
    <div class="controls">
      <button onclick="step(-1)">◀ Prev (←)</button>
      <span id="info"></span>
      <button onclick="step(1)">Next (→) ▶</button>
    </div>
    <div id="thumb-strip"></div>
  </div>
<script>
  const images = {img_data};
  const baseKey = "gallery_" + window.location.pathname;
  const idxKey = baseKey + "_idx";
  const scrollKey = baseKey + "_scroll";

  let idx = parseInt(sessionStorage.getItem(idxKey) || "0", 10);
  if (isNaN(idx) || idx < 0) idx = 0;

  let isHoveringStrip = false;
  const stripEl = document.getElementById("thumb-strip");

  function buildThumbnails() {{
    const frag = document.createDocumentFragment();
    images.forEach((item, i) => {{
      const box = document.createElement("div");
      box.className = "thumb-item";
      box.dataset.index = i;
      box.title = item.name;
      box.onclick = () => show(i, true);

      const img = document.createElement("img");
      img.src = item.url;
      img.loading = "lazy";
      img.decoding = "async";
      img.alt = item.name;

      const badge = document.createElement("span");
      badge.className = "thumb-num";
      badge.textContent = i + 1;

      box.appendChild(img);
      box.appendChild(badge);
      frag.appendChild(box);
    }});
    stripEl.appendChild(frag);
  }}

  function show(i, centerThumb = true) {{
    if (!images.length) return;
    idx = (i + images.length) % images.length;
    sessionStorage.setItem(idxKey, idx);

    document.getElementById("preview").src = images[idx].url;
    document.getElementById("info").textContent = `[ ${{idx + 1}} / ${{images.length}} ]  ${{images[idx].name}}`;

    const prevActive = stripEl.querySelector(".thumb-item.active");
    if (prevActive) prevActive.classList.remove("active");

    const currThumb = stripEl.children[idx];
    if (currThumb) {{
      currThumb.classList.add("active");
      if (centerThumb) {{
        currThumb.scrollIntoView({{ behavior: "smooth", inline: "center", block: "nearest" }});
      }}
    }}
  }}

  function step(delta) {{
    show(idx + delta, true);
  }}

  async function deleteFolder() {{
    const folderName = decodeURIComponent(window.location.pathname);
    if (!confirm(`Delete the entire folder "${{folderName}}" and everything inside it?`)) return;

    try {{
      const res = await fetch("/__delete_folder__", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ path: window.location.pathname }})
      }});
      if (res.ok) {{
        sessionStorage.removeItem(idxKey);
        sessionStorage.removeItem(scrollKey);
        window.location.href = "../";
      }} else {{
        alert("Failed to delete folder: " + (await res.text()));
      }}
    }} catch (err) {{
      alert("Error deleting folder: " + err);
    }}
  }}

  // Fast horizontal scroll using mouse wheel over thumbnail strip
  stripEl.addEventListener("wheel", (e) => {{
    if (e.deltaY !== 0) {{
      e.preventDefault();
      stripEl.scrollLeft += e.deltaY * 1.5;
    }}
  }}, {{ passive: false }});

  stripEl.addEventListener("mouseenter", () => {{ isHoveringStrip = true; }});
  stripEl.addEventListener("mouseleave", () => {{ isHoveringStrip = false; }});

  if (images.length > 0) {{
    document.getElementById("viewer").style.display = "flex";
    buildThumbnails();
    show(Math.min(idx, images.length - 1), false);

    const savedScroll = parseInt(sessionStorage.getItem(scrollKey) || "-1", 10);
    if (!isNaN(savedScroll) && savedScroll >= 0) {{
      stripEl.scrollLeft = savedScroll;
    }} else if (stripEl.children[idx]) {{
      stripEl.children[idx].scrollIntoView({{ inline: "center", block: "nearest" }});
    }}
  }}

  // Auto-reload page periodically (pauses while browsing thumbnails)
  setInterval(() => {{
    if (isHoveringStrip) return;
    sessionStorage.setItem(idxKey, idx);
    sessionStorage.setItem(scrollKey, stripEl.scrollLeft);
    window.location.reload();
  }}, {AUTO_RELOAD_MS});

  document.addEventListener("keydown", (e) => {{
    if (e.key === "ArrowRight" || e.key === "d" || e.key === "D") step(1);
    else if (e.key === "ArrowLeft" || e.key === "a" || e.key === "A") step(-1);
    else if (e.key === "Home") show(0, true);
    else if (e.key === "End") show(images.length - 1, true);
    else if (e.key === "Backspace" && "{rel_path}" !== "/") window.location.href = "../";
  }});
</script>
</body>
</html>"""

        encoded = page.encode("utf-8", "surrogateescape")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        return io.BytesIO(encoded)


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with ReusableTCPServer(("0.0.0.0", PORT), GalleryHandler) as httpd:
        print(f"Serving UI on http://0.0.0.0:{PORT}/")
        httpd.serve_forever()