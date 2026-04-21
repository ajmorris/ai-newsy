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
      <mj-text font-family="'JetBrains Mono', Menlo, monospace" color="${DB.textDim}" font-size="10px" text-transform="uppercase" letter-spacing="1px" padding="6px 0">
        <span style="background:${DB.accent};color:${DB.accentInk};padding:2px 6px;border-radius:2px;font-weight:700;">${esc(story.tag || "Story")}</span>
        &nbsp;&nbsp;${String(idx + 1).padStart(2, "0")} · ${esc(story.source || "Source")} ${story.read ? `· ${esc(story.read)}` : ""}
      </mj-text>
      <mj-text color="${DB.text}" font-size="23px" font-weight="700" line-height="1.25" padding="4px 0">
        ${esc(story.headline || "Untitled story")}
      </mj-text>
      <mj-text color="${DB.textMute}" font-size="15px" line-height="1.7" padding="2px 0 10px">
        ${esc(story.summary || "No summary available.")}
      </mj-text>
      <mj-table padding="0 0 12px">
        <tr>
          <td style="border-left:2px solid ${DB.accent};padding-left:12px;font-family:'JetBrains Mono', Menlo, monospace;color:${DB.text};font-size:12px;line-height:1.6;">
            <span style="color:${DB.accent};text-transform:uppercase;letter-spacing:1px;font-weight:700;">Why it matters</span><br/>
            ${esc(story.why || "Follow the source for details.")}
          </td>
        </tr>
      </mj-table>
      <mj-text font-family="'JetBrains Mono', Menlo, monospace" font-size="12px" padding="0 0 20px">
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
    <mj-attributes>
      <mj-all font-family="Inter, Arial, sans-serif" />
      <mj-text padding="0" />
      <mj-section padding="0" />
      <mj-column padding="0" />
    </mj-attributes>
  </mj-head>
  <mj-body background-color="${DB.bg}">
    <mj-wrapper padding="0" background-color="${DB.card}">
      <mj-section background-color="${DB.bgRaised}" padding="12px 18px" border-bottom="1px solid ${DB.border}">
        <mj-column>
          <mj-text color="${DB.textMute}" font-size="10px" font-family="'JetBrains Mono', Menlo, monospace">
            ● ● ● &nbsp;&nbsp; inbox · ai-news-daily@digest · ${esc(payload.dateLabel || "")} · 06:00 am &nbsp;&nbsp; #${esc(issueLabel)}
          </mj-text>
        </mj-column>
      </mj-section>
      <mj-section padding="28px 28px 18px">
        <mj-column>
          <mj-text color="${DB.text}" font-size="14px" font-weight="700">AI News Daily</mj-text>
          <mj-text color="${DB.textDim}" font-size="10px" font-family="'JetBrains Mono', Menlo, monospace" text-transform="uppercase" letter-spacing="1px" padding="6px 0 12px">
            Issue ${esc(issueLabel)} · ${stories.length} stories
          </mj-text>
          <mj-text color="${DB.text}" font-size="34px" font-weight="700" line-height="1.1">
            ${esc(payload.heroHeadline || "The AI feed, distilled.")}
          </mj-text>
          <mj-text color="${DB.textMute}" font-size="14px" line-height="1.6" padding="12px 0 0">
            ${esc(payload.intro || "")}
          </mj-text>
        </mj-column>
      </mj-section>
      <mj-section background-color="${DB.bgRaised}" padding="18px 28px" border-top="1px solid ${DB.borderSoft}" border-bottom="1px solid ${DB.borderSoft}">
        <mj-column>
          <mj-text font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="10px" text-transform="uppercase" letter-spacing="2px" font-weight="700" padding="0 0 8px">
            ◆ TL;DR
          </mj-text>
          ${tldrItems}
        </mj-column>
      </mj-section>
      <mj-section padding="24px 28px 8px">
        <mj-column>
          ${storyItems}
        </mj-column>
      </mj-section>
      <mj-section padding="4px 28px 24px">
        <mj-column>
          <mj-text font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="10px" text-transform="uppercase" letter-spacing="2px" font-weight="700" padding="0 0 10px">
            ◆ Quick hits
          </mj-text>
          ${quickHitItems}
        </mj-column>
      </mj-section>
      <mj-section background-color="${DB.bgRaised}" padding="24px 28px" border-top="1px solid ${DB.border}">
        <mj-column>
          <mj-text font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="10px" text-transform="uppercase" letter-spacing="2px" font-weight="700">
            ◆ End of edition
          </mj-text>
          <mj-text color="${DB.text}" font-size="20px" font-weight="700" padding="8px 0 4px">See you tomorrow at 06:00.</mj-text>
          <mj-text color="${DB.textMute}" font-size="13px" padding="0 0 14px">Got a tip? Just reply — a human reads every one.</mj-text>
          <mj-button background-color="${DB.accent}" color="${DB.accentInk}" font-family="'JetBrains Mono', Menlo, monospace" font-size="12px" font-weight="700" text-transform="uppercase" inner-padding="10px 16px" border-radius="2px" href="${esc(payload.forwardUrl || payload.archiveUrl || "#")}">
            Forward to a friend →
          </mj-button>
        </mj-column>
      </mj-section>
      <mj-section padding="16px 28px 24px" border-top="1px solid ${DB.borderSoft}">
        <mj-column>
          <mj-text font-family="'JetBrains Mono', Menlo, monospace" color="${DB.textDim}" font-size="10px" line-height="1.8">
            © 2026 AI News Daily · v4.137<br/>
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
