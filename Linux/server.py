import html
import http.server
import io
import json
import os
import re
import socketserver
import urllib.parse
from http import HTTPStatus

PORT = 1711
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
  body {{ background: #121212; color: #eee; font-family: monospace; height: 100vh; display: flex; flex-direction: column; }}
  header {{ background: #1e1e1e; padding: 10px 14px; border-bottom: 1px solid #333; }}
  .path {{ font-size: 14px; color: #8ab4f8; margin-bottom: 8px; }}
  .links {{ display: flex; flex-wrap: wrap; gap: 6px; max-height: 28vh; overflow-y: auto; }}
  .chip {{ text-decoration: none; padding: 4px 9px; border-radius: 4px; font-size: 13px; }}
  .dir {{ background: #263238; color: #80cbc4; border: 1px solid #37474f; }}
  .dir:hover {{ background: #37474f; }}
  .file {{ background: #222; color: #bbb; border: 1px solid #333; }}
  .file:hover {{ background: #333; }}
  #viewer {{ flex: 1; display: none; flex-direction: column; align-items: center; justify-content: center; padding: 10px; overflow: hidden; }}
  #viewer img {{ max-width: 96vw; max-height: calc(100vh - 150px); object-fit: contain; border: 1px solid #333; background: #000; }}
  .controls {{ margin-top: 10px; display: flex; align-items: center; gap: 14px; font-size: 14px; }}
  button {{ background: #2a2a2a; color: #fff; border: 1px solid #555; padding: 6px 14px; border-radius: 4px; cursor: pointer; font-family: monospace; }}
  button:hover {{ background: #3d3d3d; }}
  #info {{ color: #ffd54f; }}
</style>
</head>
<body>
  <header>
    <div class="path">{title}</div>
    <div class="links">{''.join(nav_links)}</div>
  </header>
  <div id="viewer">
    <img id="preview" src="" alt="">
    <div class="controls">
      <button onclick="step(-1)">◀ Prev (←)</button>
      <span id="info"></span>
      <button onclick="step(1)">Next (→) ▶</button>
    </div>
  </div>
<script>
  const images = {img_data};
  let idx = 0;

  function show(i) {{
    if (!images.length) return;
    idx = (i + images.length) % images.length;
    document.getElementById("preview").src = images[idx].url;
    document.getElementById("info").textContent = `[ ${{idx + 1}} / ${{images.length}} ]  ${{images[idx].name}}`;
  }}

  function step(delta) {{
    show(idx + delta);
  }}

  if (images.length > 0) {{
    document.getElementById("viewer").style.display = "flex";
    show(0);
  }}

  document.addEventListener("keydown", (e) => {{
    if (e.key === "ArrowRight" || e.key === "d" || e.key === "D") step(1);
    else if (e.key === "ArrowLeft" || e.key === "a" || e.key === "A") step(-1);
    else if (e.key === "Home") show(0);
    else if (e.key === "End") show(images.length - 1);
    else if (e.key === "Backspace" && "{rel_path}" !== "/") window.location.href = "../";
  }});
</script>
</body>
</html>"""

        encoded = page.encode("utf-8", "surrogateescape")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        return io.BytesIO(encoded)


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with ReusableTCPServer(("0.0.0.0", PORT), GalleryHandler) as httpd:
        print(f"Serving UI on http://0.0.0.0:{PORT}/")
        httpd.serve_forever()
