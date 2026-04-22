import fs from "node:fs";
import mjml2html from "mjml";

const inputPath = process.argv[2];
if (!inputPath) {
  process.stderr.write("Missing payload path\n");
  process.exit(1);
}

const payload = JSON.parse(fs.readFileSync(inputPath, "utf8"));

const esc = (value = "") =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const DB = {
  bg: "#0b0b0c",
  bgRaised: "#121214",
  card: "#17171a",
  border: "#26262b",
  borderSoft: "#1d1d21",
  text: "#f4f3ef",
  textMute: "#a3a099",
  textDim: "#6b6a65",
  accent: "#39ff88",
  accentInk: "#0b0b0c",
  danger: "#ff5a4e",
  amber: "#ffb930"
};

const stories = (payload.stories || []).slice(0, 8);
const quickHits = payload.quickHits || [];
const issueLabel = payload.issueNumber || "00137";
const heroHeadline = payload.heroHeadline || "The AI feed, distilled.";

const tldrItems = stories
  .map(
    (story, idx) => `
      <mj-text font-family="'JetBrains Mono', Menlo, monospace" color="${DB.textDim}" font-size="11px" padding="5px 0">
        ${String(idx + 1).padStart(2, "0")} · <span style="color:${DB.text};">${esc(story.headline || "Untitled story")}</span>${story.read ? ` · ${esc(story.read)}` : ""}
      </mj-text>
    `
  )
  .join("");

const storyItems = stories
  .map(
    (story, idx) => `
      <mj-text font-family="'JetBrains Mono', Menlo, monospace" color="${DB.textDim}" font-size="10px" text-transform="uppercase" letter-spacing="1.4px" padding="0 0 10px">
        <span style="background:${DB.accent};color:${DB.accentInk};padding:2px 7px;border-radius:2px;font-weight:700;">${esc(story.tag || "Story")}</span>
        &nbsp;&nbsp;${String(idx + 1).padStart(2, "0")} · ${esc(story.source || "Source")} ${story.read ? `· ${esc(story.read)}` : ""}
      </mj-text>
      ${
        story.imageUrl
          ? `<mj-image src="${esc(story.imageUrl)}" alt="${esc(story.headline || "Story image")}" padding="0 0 14px" fluid-on-mobile="true" />`
          : ""
      }
      <mj-text color="${DB.text}" font-size="24px" font-weight="700" line-height="1.2" padding="0 0 8px" letter-spacing="-0.6px">
        ${esc(story.headline || "Untitled story")}
      </mj-text>
      <mj-text color="${DB.textMute}" font-size="15px" line-height="1.65" padding="0 0 14px">
        ${esc(story.summary || "No summary available.")}
      </mj-text>
      <mj-table padding="0 0 14px">
        <tr>
          <td style="border-left:2px solid ${DB.accent};padding-left:12px;font-family:'JetBrains Mono', Menlo, monospace;color:${DB.text};font-size:12px;line-height:1.6;">
            <span style="display:block;color:${DB.accent};text-transform:uppercase;letter-spacing:1.8px;font-size:10px;font-weight:700;margin-bottom:4px;">Why it matters</span>
            ${esc(story.why || "Follow the source for details.")}
          </td>
        </tr>
      </mj-table>
      <mj-text font-family="'JetBrains Mono', Menlo, monospace" font-size="12px" padding="0 0 22px" letter-spacing="0.5px">
        <a href="${esc(story.url || "#")}" style="color:${DB.accent};text-decoration:underline;">→ read at ${esc((story.source || "source").toLowerCase())}</a>
      </mj-text>
      <mj-divider border-color="${DB.borderSoft}" />
    `
  )
  .join("");

const quickHitItems = quickHits
  .map(
    (item) => `
      <mj-text color="${DB.textMute}" font-size="14px" padding="5px 0">
        <span style="color:${DB.accent};font-family:'JetBrains Mono', Menlo, monospace;">»</span> ${esc(item)}
      </mj-text>
    `
  )
  .join("");

const mjml = `
<mjml>
  <mj-head>
    <mj-preview>${esc(payload.subject || "AI News Daily")}</mj-preview>
    <mj-font name="Inter" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800" />
    <mj-font name="JetBrains Mono" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700" />
    <mj-font name="Instrument Serif" href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@1" />
    <mj-attributes>
      <mj-all font-family="Inter, Arial, sans-serif" />
      <mj-text padding="0" />
      <mj-section padding="0" />
      <mj-column padding="0" />
    </mj-attributes>
  </mj-head>
  <mj-body background-color="${DB.bg}">
    <mj-wrapper padding="0" background-color="${DB.card}" border="1px solid ${DB.border}">
      <mj-section background-color="${DB.bgRaised}" padding="30px 36px 22px" border-bottom="1px solid ${DB.borderSoft}">
        <mj-column>
          <mj-table padding="0 0 18px">
            <tr>
              <td style="width:28px;vertical-align:middle;">
                <div style="width:28px;height:28px;background:${DB.accent};color:${DB.accentInk};text-align:center;line-height:28px;border-radius:2px;font-family:'JetBrains Mono',Menlo,monospace;font-size:14px;font-weight:800;box-shadow:0 0 14px rgba(57,255,136,0.45);">◼</div>
              </td>
              <td style="vertical-align:middle;padding-left:10px;">
                <div style="font-family:Inter,Arial,sans-serif;color:${DB.text};font-size:14px;font-weight:700;">AI News Daily</div>
              </td>
              <td style="vertical-align:middle;text-align:right;">
                <div style="font-family:'JetBrains Mono',Menlo,monospace;color:${DB.textDim};font-size:10px;letter-spacing:1px;text-transform:uppercase;">${esc(payload.subject || `ISSUE ${issueLabel} · ${stories.length} STORIES · 11 MIN READ`)}</div>
              </td>
            </tr>
          </mj-table>
          <mj-text color="${DB.text}" font-size="36px" font-weight="700" line-height="1.1" letter-spacing="-1.5px" padding="0 0 12px">
            ${esc(heroHeadline)}
          </mj-text>
          <mj-text color="${DB.textMute}" font-size="14px" line-height="1.6" padding="0">
            ${esc(payload.intro || "")}
          </mj-text>
        </mj-column>
      </mj-section>
      <mj-section background-color="${DB.bgRaised}" padding="22px 36px" border-bottom="1px solid ${DB.borderSoft}">
        <mj-column>
          <mj-text font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="10px" text-transform="uppercase" letter-spacing="2px" font-weight="700" padding="0 0 8px">
            ◆ TL;DR
          </mj-text>
          ${tldrItems}
        </mj-column>
      </mj-section>
      <mj-section padding="24px 36px 10px">
        <mj-column>
          ${storyItems}
        </mj-column>
      </mj-section>
      <mj-section padding="2px 36px 30px">
        <mj-column>
          <mj-text font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="10px" text-transform="uppercase" letter-spacing="2px" font-weight="700" padding="0 0 10px">
            ◆ Quick hits
          </mj-text>
          ${quickHitItems}
        </mj-column>
      </mj-section>
      <mj-section background-color="${DB.bgRaised}" padding="28px 36px" border-top="1px solid ${DB.border}">
        <mj-column>
          <mj-text font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="10px" text-transform="uppercase" letter-spacing="2px" font-weight="700">
            ◆ End of edition
          </mj-text>
          <mj-text color="${DB.text}" font-size="20px" font-weight="700" letter-spacing="-0.4px" padding="5px 0 5px">See you tomorrow at 8:00.</mj-text>
          <mj-text color="${DB.textMute}" font-size="13px" padding="0 0 14px">Got a tip? Just reply — a human reads every one.</mj-text>
          <mj-button background-color="${DB.accent}" color="${DB.accentInk}" font-family="'JetBrains Mono', Menlo, monospace" font-size="12px" font-weight="700" text-transform="uppercase" letter-spacing="1.2px" inner-padding="10px 16px" border-radius="2px" href="${esc(payload.forwardUrl || payload.archiveUrl || "#")}">
            Forward to a friend →
          </mj-button>
        </mj-column>
      </mj-section>
      <mj-section padding="18px 36px 24px" border-top="1px solid ${DB.borderSoft}">
        <mj-column>
          <mj-text font-family="'JetBrains Mono', Menlo, monospace" color="${DB.textDim}" font-size="10px" line-height="1.8">
            © 2026 AI News Daily · v4.137 · status: operational <span style="color:${DB.accent}">●</span><br/>
            <a href="${esc(payload.unsubscribeUrl || "#")}" style="color:${DB.textMute};">unsubscribe</a> ·
            <a href="${esc(payload.viewInBrowserUrl || "#")}" style="color:${DB.textMute};">view in browser</a> ·
            <a href="${esc(payload.archiveUrl || "#")}" style="color:${DB.textMute};">archive</a>
          </mj-text>
        </mj-column>
      </mj-section>
    </mj-wrapper>
  </mj-body>
</mjml>
`;

const output = mjml2html(mjml);
if (output.errors && output.errors.length > 0) {
  process.stderr.write(`${JSON.stringify(output.errors)}\n`);
  process.exit(1);
}

process.stdout.write(output.html);
