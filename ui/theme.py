"""Visual theme: CSS variables for light/dark, chat layout, code highlighting, small scripts."""
from __future__ import annotations

from nicegui import ui
from pygments.formatters import HtmlFormatter

_BASE_CSS = """
:root {
  --bg:#F1F4F8; --panel:#FFFFFF; --side:#E7ECF3; --ink:#18212D; --muted:#5E6C7E;
  --line:#D5DCE6; --accent:#2B47C7; --accent-soft:#E2E8FB; --user:#1E2B4D; --user-ink:#FFFFFF;
  --code-bg:#F4F6FA; --ok:#1E9E5A; --warn:#D68A0B; --bad:#C93B3B;
  --sans:"Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  --mono:"Cascadia Code","Cascadia Mono",Consolas,"SF Mono",Menlo,monospace;
}
body.body--dark {
  --bg:#10141B; --panel:#171D27; --side:#0C1016; --ink:#E4E9F0; --muted:#8F9BAD;
  --line:#27303F; --accent:#8CA0FF; --accent-soft:#1F2842; --user:#2A3A6B; --user-ink:#F4F6FF;
  --code-bg:#0B0F15;
}
body { background:var(--bg); color:var(--ink); font-family:var(--sans); }
.q-layout, .q-page-container { background:var(--bg); }
.q-drawer { background:var(--side) !important; color:var(--ink); }
.q-header { background:var(--bg) !important; color:var(--ink); border-bottom:1px solid var(--line); }
.q-footer { background:var(--bg) !important; color:var(--ink); border-top:0; }
.q-dialog .q-card { background:var(--panel); color:var(--ink); max-width:none !important; }
.q-field--outlined .q-field__control { background:var(--panel); }

.omc-brand { font-size:1.08rem; font-weight:650; letter-spacing:.01em; }
.omc-logo { width:30px; height:30px; border-radius:9px; display:grid; place-items:center;
  background:var(--accent); color:#fff; font-size:18px; }
.omc-section { font-size:.78rem; font-weight:600; color:var(--muted); margin-top:.35rem; }
.omc-meta { font-size:.76rem; color:var(--muted); line-height:1.35; }
.omc-mono { font-family:var(--mono); font-size:.74rem; color:var(--muted); word-break:break-all; }
.omc-model-card { border:1px solid var(--line); border-radius:10px; padding:.6rem .7rem; background:var(--panel); }
.omc-dot { width:9px; height:9px; border-radius:50%; display:inline-block; background:var(--muted); flex:none; }
.omc-dot-available { background:var(--ok); } .omc-dot-unavailable { background:var(--bad); }
.omc-dot-unknown { background:var(--warn); }

.omc-conv { padding:.42rem .55rem; border-radius:8px; cursor:pointer; min-height:36px; }
.omc-conv:hover { background:var(--accent-soft); }
.omc-conv.active { background:var(--accent-soft); box-shadow:inset 3px 0 0 var(--accent); }
.omc-conv-title { font-size:.88rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }

.omc-thread { max-width:50rem; margin:0 auto; padding:1.25rem .5rem 2.5rem; }
.omc-welcome { margin:7vh auto 0; max-width:38rem; text-align:left; }
.omc-welcome h1 { font-size:1.9rem; font-weight:650; margin:0 0 .4rem; letter-spacing:-.01em; }
.omc-suggest { border:1px solid var(--line); background:var(--panel); border-radius:10px; padding:.6rem .8rem;
  font-size:.88rem; text-align:left; cursor:pointer; }
.omc-suggest:hover { border-color:var(--accent); }

.omc-msg-user { max-width:85%; background:var(--user); color:var(--user-ink); border-radius:16px 16px 4px 16px;
  padding:.65rem .95rem; white-space:pre-wrap; word-break:break-word; line-height:1.5; }
.omc-avatar { width:30px; height:30px; border-radius:9px; display:grid; place-items:center; flex:none;
  font-size:.72rem; font-weight:700; letter-spacing:.02em; }
.omc-model-name { font-size:.8rem; font-weight:600; }
.omc-notice { border:1px solid var(--line); border-left:3px solid var(--warn); background:var(--panel);
  border-radius:8px; padding:.55rem .8rem; font-size:.82rem; color:var(--muted); }
.omc-error { border:1px solid var(--bad); background:var(--panel); border-radius:10px; padding:.7rem .9rem; }

.omc-md { line-height:1.62; word-break:break-word; min-width:0; max-width:100%; }
.omc-md > :first-child { margin-top:0; } .omc-md > :last-child { margin-bottom:0; }
.omc-md p { margin:.55em 0; } .omc-md ul, .omc-md ol { padding-left:1.4rem; margin:.5em 0; }
.omc-md h1, .omc-md h2, .omc-md h3 { margin:1em 0 .4em; line-height:1.25; }
.omc-md a { color:var(--accent); }
.omc-md blockquote { margin:.6em 0; padding:.1em .9em; border-left:3px solid var(--line); color:var(--muted); }
.omc-md table { border-collapse:collapse; display:block; overflow-x:auto; max-width:100%; }
.omc-md th, .omc-md td { border:1px solid var(--line); padding:.35rem .6rem; }
.omc-md code { font-family:var(--mono); font-size:.86em; background:var(--code-bg); padding:.1em .35em; border-radius:5px; }
.omc-md pre, .omc-md .codehilite, .omc-md .highlight { background:var(--code-bg) !important; border:1px solid var(--line);
  border-radius:10px; overflow-x:auto; }
.omc-md pre { padding:.8rem 1rem; margin:.7em 0; font-family:var(--mono); font-size:.84rem; line-height:1.5; }
.omc-md .codehilite pre, .omc-md .highlight pre { border:0; margin:0; }
.omc-md pre code { background:transparent; padding:0; font-size:inherit; }
.omc-codewrap { position:relative; }
.omc-copy { position:absolute; top:6px; right:8px; font:600 .7rem var(--sans); border:1px solid var(--line);
  background:var(--panel); color:var(--muted); border-radius:6px; padding:2px 8px; cursor:pointer; }
.omc-copy:hover { color:var(--ink); border-color:var(--accent); }
.omc-streaming .omc-md > :last-child::after { content:"\\25AE"; color:var(--accent); margin-left:2px;
  animation:omc-blink 1s steps(2,start) infinite; }
@keyframes omc-blink { to { visibility:hidden; } }
@media (prefers-reduced-motion: reduce) { .omc-streaming .omc-md > :last-child::after { animation:none; } }

.omc-footer { padding:.4rem .75rem .8rem; }
.omc-composer { max-width:50rem; margin:0 auto; }
.omc-input .q-field__control { border-radius:18px; }
.omc-input textarea { max-height:9rem; line-height:1.45; }
.omc-foot-note { font-size:.7rem; color:var(--muted); text-align:center; }

.q-btn { text-transform:none; letter-spacing:0; font-family:var(--sans); }
.q-header { backdrop-filter:blur(10px); background:color-mix(in srgb, var(--bg) 82%, transparent) !important; }
.omc-chip { border:1px solid var(--line); border-radius:999px; padding:.22rem .8rem .22rem .3rem;
  background:var(--panel); font-size:.8rem; font-weight:600; }

.omc-hero { font-size:clamp(1.8rem,4.2vw,2.6rem); font-weight:700; letter-spacing:-.025em; line-height:1.1; }
.omc-lede { font-size:1rem; color:var(--muted); line-height:1.55; max-width:34rem; }
.omc-welcome { margin:6vh auto 0; max-width:46rem; }
.omc-model-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(14.5rem,1fr)); gap:.75rem; width:100%; }
.omc-mcard { background:var(--panel); border:1px solid var(--line); border-top:3px solid hsl(var(--h) 52% 46%);
  border-radius:12px; padding:.8rem .9rem; cursor:pointer; display:flex; flex-direction:column; gap:.45rem;
  transition:box-shadow .15s, transform .15s; }
.omc-mcard:hover { box-shadow:0 6px 18px rgba(16,24,40,.12); transform:translateY(-1px); }
.omc-mcard.selected { box-shadow:0 0 0 2px hsl(var(--h) 56% 50%); }
.omc-mcard-name { font-size:.95rem; font-weight:650; line-height:1.2; }
.omc-suggest { border-radius:999px; padding:.4rem .85rem; font-size:.83rem; }
@media (prefers-reduced-motion: reduce) { .omc-mcard { transition:none; } .omc-mcard:hover { transform:none; } }

.omc-ai { border-left:3px solid hsl(var(--h) 50% 46%); padding-left:1rem; }
.omc-md { font-size:.98rem; }
.omc-thread { padding-top:1.5rem; gap:1.6rem; }

.omc-box { background:var(--panel); border:1px solid var(--line); border-radius:20px;
  padding:.3rem .4rem .3rem 1rem; box-shadow:0 8px 28px rgba(16,24,40,.10); }
.omc-box:focus-within { border-color:var(--accent); }
.omc-input .q-field__control { background:transparent !important; }
.omc-input .q-field__native { padding-top:.45rem; padding-bottom:.45rem; font-size:.98rem; }
.omc-notice { border:1px solid var(--line); border-left:3px solid var(--warn); background:var(--panel);
  border-radius:10px; padding:.6rem .85rem; font-size:.86rem; color:var(--ink); }
"""

_HEAD_JS = """
<script>
(function () {
  function addCopyButtons() {
    document.querySelectorAll('.omc-md pre').forEach(function (pre) {
      if (pre.dataset.omcCopy) return;
      pre.dataset.omcCopy = '1';
      var host = pre.parentElement && pre.parentElement.classList.contains('codehilite') ? pre.parentElement : pre;
      host.classList.add('omc-codewrap');
      var btn = document.createElement('button');
      btn.type = 'button'; btn.className = 'omc-copy'; btn.textContent = 'Copy';
      btn.addEventListener('click', function () {
        navigator.clipboard.writeText(pre.innerText).then(function () {
          btn.textContent = 'Copied';
          setTimeout(function () { btn.textContent = 'Copy'; }, 1500);
        });
      });
      host.appendChild(btn);
    });
  }
  var pending = false;
  new MutationObserver(function () {
    if (pending) return; pending = true;
    requestAnimationFrame(function () { pending = false; addCopyButtons(); });
  }).observe(document.documentElement, { childList: true, subtree: true });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.target && e.target.matches &&
        e.target.matches('.omc-input textarea')) {
      e.preventDefault();
      var b = document.getElementById('omc-send');
      if (b) b.click();
    }
  }, true);
})();
</script>
"""


def _highlight_css() -> str:
    light = HtmlFormatter(style="friendly")
    dark = HtmlFormatter(style="monokai")
    parts = []
    for cls in (".codehilite", ".highlight"):
        parts.append(light.get_style_defs(f".omc-md {cls}"))
        parts.append(dark.get_style_defs(f"body.body--dark .omc-md {cls}"))
    return "\n".join(parts)


def apply_theme() -> None:
    ui.colors(primary="#2B47C7")
    ui.add_css(_BASE_CSS + _highlight_css())
    ui.add_head_html(_HEAD_JS)
