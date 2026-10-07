import fs from "node:fs";
import mjml2html from "mjml";

const inputPath = process.argv[2];
if (!inputPath) {
  process.stderr.write("Missing payload path\n");
  process.exit(1);
}

const payload = JSON.parse(fs.readFileSync(inputPath, "utf8"));
const tokens = JSON.parse(
  fs.readFileSync(new URL("./tokens.json", import.meta.url), "utf8")
);

const esc = (value = "") =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const DB = tokens.light;
const DARK = tokens.dark;

const darkModeCss = `
    :root { color-scheme: light dark; supported-color-schemes: light dark; }
    @media (prefers-color-scheme: dark) {
      .dm-page, .dm-page > div, .dm-page > table { background-color: ${DARK.bg} !important; }
      .dm-card, .dm-card > table { background-color: ${DARK.card} !important; border-color: ${DARK.border} !important; }
      .dm-raised, .dm-raised > table { background-color: ${DARK.bgRaised} !important; }
      .dm-text div, .dm-text p, .dm-text span { color: ${DARK.text} !important; }
      .dm-mute div, .dm-mute p, .dm-mute span { color: ${DARK.textMute} !important; }
      .dm-dim div, .dm-dim p, .dm-dim span { color: ${DARK.textDim} !important; }
      .dm-accent div, .dm-accent p, .dm-accent span { color: ${DARK.accent} !important; }
      .dm-link { color: ${DARK.accent} !important; }
      .dm-chip { background-color: ${DARK.accent} !important; color: ${DARK.accentInk} !important; }
      .dm-button table, .dm-button a { background-color: ${DARK.accent} !important; color: ${DARK.accentInk} !important; }
    }
    [data-ogsc] .dm-text div, [data-ogsc] .dm-text p, [data-ogsb] .dm-text div, [data-ogsb] .dm-text p { color: ${DARK.text} !important; }
    [data-ogsc] .dm-mute div, [data-ogsc] .dm-mute p, [data-ogsb] .dm-mute div, [data-ogsb] .dm-mute p { color: ${DARK.textMute} !important; }
    [data-ogsc] .dm-dim div, [data-ogsb] .dm-dim div { color: ${DARK.textDim} !important; }
    [data-ogsc] .dm-accent div, [data-ogsb] .dm-accent div { color: ${DARK.accent} !important; }
    [data-ogsc] .dm-link, [data-ogsb] .dm-link { color: ${DARK.accent} !important; }
    [data-ogsc] .dm-page, [data-ogsb] .dm-page, [data-ogsc] .dm-card, [data-ogsb] .dm-card { background-color: ${DARK.bg} !important; }
    [data-ogsc] .dm-raised, [data-ogsb] .dm-raised { background-color: ${DARK.bgRaised} !important; }
    [data-ogsc] .dm-chip, [data-ogsb] .dm-chip { background-color: ${DARK.accent} !important; color: ${DARK.accentInk} !important; }
`;

const stories = (payload.stories || []).slice(0, 8);
const tweetHeadlines = payload.tweetHeadlines || [];
const communityHeadlines = payload.communityHeadlines || [];
const issueLabel = payload.issueNumber || "00137";
const heroHeadline = payload.heroHeadline || "The AI feed, distilled.";

const renderQuickHitHeadline = (item) => {
  const headline =
    item && typeof item === "object"
      ? String(item.headline || "").trim()
      : String(item || "").trim();
  const url =
    item && typeof item === "object" ? String(item.url || "").trim() : "";

  if (!headline) {
    return "";
  }
  if (!url) {
    return esc(headline);
  }

  const anchorMatch = /__(.+?)__/.exec(headline);
  if (!anchorMatch || anchorMatch.index === undefined) {
    return `${esc(headline)} <a class="dm-link" href="${esc(url)}" style="color:${DB.accent};text-decoration:underline;">Source</a>`;
  }

  const anchorText = anchorMatch[1];
  const before = headline.slice(0, anchorMatch.index);
  const after = headline.slice(anchorMatch.index + anchorMatch[0].length);

  return `${esc(before)}<a class="dm-link" href="${esc(url)}" style="color:${DB.accent};text-decoration:underline;">${esc(anchorText)}</a>${esc(after)}`;
};

const tldrItems = stories
  .map(
    (story, idx) => `
      <mj-text css-class="dm-dim" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.textDim}" font-size="11px" padding="5px 0">
        ${String(idx + 1).padStart(2, "0")} · <span class="dm-text" style="color:${DB.text};">${esc(story.headline || "Untitled story")}</span>${story.read ? ` · ${esc(story.read)}` : ""}
      </mj-text>
    `
  )
  .join("");

const storyItems = stories
  .map(
    (story, idx) => `
      <mj-text css-class="dm-dim" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.textDim}" font-size="10px" text-transform="uppercase" letter-spacing="1.4px" padding="0 0 10px">
        <span class="dm-chip" style="background:${DB.accent};color:${DB.accentInk};padding:2px 7px;border-radius:2px;font-weight:700;">${esc(story.tag || "Story")}</span>
        &nbsp;&nbsp;${String(idx + 1).padStart(2, "0")} · ${esc(story.source || "Source")} ${story.read ? `· ${esc(story.read)}` : ""}
      </mj-text>
      ${
        story.imageUrl
          ? `<mj-image src="${esc(story.imageUrl)}" alt="${esc(story.headline || "Story image")}" padding="0 0 14px" fluid-on-mobile="true" />`
          : ""
      }
      <mj-text css-class="dm-text" color="${DB.text}" font-size="24px" font-weight="700" line-height="1.2" padding="0 0 8px" letter-spacing="-0.6px">
        ${esc(story.headline || "Untitled story")}
      </mj-text>
      <mj-text css-class="dm-mute" color="${DB.textMute}" font-size="15px" line-height="1.65" padding="0 0 14px">
        ${esc(story.summary || "No summary available.")}
      </mj-text>
      <mj-table padding="0 0 14px">
        <tr>
          <td class="dm-text" style="border-left:2px solid ${DB.accent};padding-left:12px;font-family:'JetBrains Mono', Menlo, monospace;color:${DB.text};font-size:12px;line-height:1.6;">
            <span class="dm-accent" style="display:block;color:${DB.accent};text-transform:uppercase;letter-spacing:1.8px;font-size:10px;font-weight:700;margin-bottom:4px;">Why it matters</span>
            ${esc(story.why || "Follow the source for details.")}
          </td>
        </tr>
      </mj-table>
      <mj-text font-family="'JetBrains Mono', Menlo, monospace" font-size="12px" padding="0 0 22px" letter-spacing="0.5px">
        <a class="dm-link" href="${esc(story.url || "#")}" style="color:${DB.accent};text-decoration:underline;">→ read at ${esc((story.source || "source").toLowerCase())}</a>
      </mj-text>
      <mj-divider border-color="${DB.borderSoft}" />
    `
  )
  .join("");

const renderQuickHitSection = (title, items, padding) => {
  const rendered = (items || [])
    .map(
      (item) => `
      <mj-text css-class="dm-mute" color="${DB.textMute}" font-size="14px" padding="5px 0">
        <span style="color:${DB.accent};font-family:'JetBrains Mono', Menlo, monospace;">»</span> ${renderQuickHitHeadline(item)}
      </mj-text>
    `
    )
    .join("");
  if (!rendered.trim()) {
    return "";
  }
  return `<mj-section padding="${padding}">
        <mj-column>
          <mj-text css-class="dm-accent" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="10px" text-transform="uppercase" letter-spacing="2px" font-weight="700" padding="0 0 10px">
            ◆ ${esc(title)}
          </mj-text>
          ${rendered}
        </mj-column>
      </mj-section>`;
};

const tweetSection = renderQuickHitSection(
  "Here's what's going on in Twitter/X",
  tweetHeadlines,
  "2px 36px 18px"
);
const communitySection = renderQuickHitSection(
  "Here's what we're hearing from the community",
  communityHeadlines,
  "2px 36px 30px"
);
const extraQuickHitSections = (payload.quickHitSections || [])
  .map((section) =>
    renderQuickHitSection(section.title || "More", section.items || [], "2px 36px 18px")
  )
  .join("");

const mjml = `
<mjml>
  <mj-head>
    <mj-preview>${esc(payload.subject || "AI News Daily")}</mj-preview>
    <mj-font name="Inter" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800" />
    <mj-font name="JetBrains Mono" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700" />
    <mj-font name="Instrument Serif" href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@1" />
    <mj-raw>
      <meta name="color-scheme" content="light dark" />
      <meta name="supported-color-schemes" content="light dark" />
      <style>${darkModeCss}</style>
    </mj-raw>
    <mj-attributes>
      <mj-all font-family="Inter, Arial, sans-serif" />
      <mj-text padding="0" />
      <mj-section padding="0" />
      <mj-column padding="0" />
    </mj-attributes>
  </mj-head>
  <mj-body background-color="${DB.bg}" css-class="dm-page">
    <mj-wrapper padding="0" background-color="${DB.card}" border="1px solid ${DB.border}" css-class="dm-card">
      <mj-section background-color="${DB.bgRaised}" padding="30px 36px 22px" border-bottom="1px solid ${DB.borderSoft}" css-class="dm-raised">
        <mj-column>
          <mj-table padding="0 0 18px">
            <tr>
              <td style="width:28px;vertical-align:middle;">
                <div class="dm-chip" style="width:28px;height:28px;background:${DB.accent};color:${DB.accentInk};text-align:center;line-height:28px;border-radius:2px;font-family:'JetBrains Mono',Menlo,monospace;font-size:14px;font-weight:800;">◼</div>
              </td>
              <td style="vertical-align:middle;padding-left:10px;">
                <div class="dm-text" style="font-family:Inter,Arial,sans-serif;color:${DB.text};font-size:14px;font-weight:700;">AI News Daily</div>
              </td>
              <td style="vertical-align:middle;text-align:right;">
                <div class="dm-dim" style="font-family:'JetBrains Mono',Menlo,monospace;color:${DB.textDim};font-size:10px;letter-spacing:1px;text-transform:uppercase;">${esc(payload.subject || `ISSUE ${issueLabel} · ${stories.length} STORIES · 11 MIN READ`)}</div>
              </td>
            </tr>
          </mj-table>
          <mj-text css-class="dm-text" color="${DB.text}" font-size="36px" font-weight="700" line-height="1.1" letter-spacing="-1.5px" padding="0 0 12px">
            ${esc(heroHeadline)}
          </mj-text>
          <mj-text css-class="dm-mute" color="${DB.textMute}" font-size="14px" line-height="1.6" padding="0">
            ${esc(payload.intro || "")}
          </mj-text>
        </mj-column>
      </mj-section>
      <mj-section background-color="${DB.bgRaised}" padding="22px 36px" border-bottom="1px solid ${DB.borderSoft}" css-class="dm-raised">
        <mj-column>
          <mj-text css-class="dm-accent" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="10px" text-transform="uppercase" letter-spacing="2px" font-weight="700" padding="0 0 8px">
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
      ${tweetSection}
      ${communitySection}
      ${extraQuickHitSections}
      <mj-section background-color="${DB.bgRaised}" padding="28px 36px" border-top="1px solid ${DB.border}" css-class="dm-raised">
        <mj-column>
          <mj-text css-class="dm-accent" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="10px" text-transform="uppercase" letter-spacing="2px" font-weight="700">
            ◆ End of edition
          </mj-text>
          <mj-text css-class="dm-text" color="${DB.text}" font-size="20px" font-weight="700" letter-spacing="-0.4px" padding="5px 0 5px">See you tomorrow.</mj-text>
          <mj-text css-class="dm-mute" color="${DB.textMute}" font-size="13px" padding="0 0 14px">Got a tip? Just reply — a human reads every one.</mj-text>
          <mj-button css-class="dm-button" background-color="${DB.accent}" color="${DB.accentInk}" font-family="'JetBrains Mono', Menlo, monospace" font-size="12px" font-weight="700" text-transform="uppercase" letter-spacing="1.2px" inner-padding="10px 16px" border-radius="2px" href="${esc(payload.forwardUrl || payload.archiveUrl || "#")}">
            Forward to a friend →
          </mj-button>
        </mj-column>
      </mj-section>
      <mj-section padding="18px 36px 24px" border-top="1px solid ${DB.borderSoft}">
        <mj-column>
          <mj-text css-class="dm-dim" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.textDim}" font-size="10px" line-height="1.8">
            © 2026 AI News Daily · v4.137 · status: operational <span class="dm-accent" style="color:${DB.accent}">●</span><br/>
            <a class="dm-link" href="${esc(payload.unsubscribeUrl || "#")}" style="color:${DB.textMute};">unsubscribe</a> ·
            <a class="dm-link" href="${esc(payload.viewInBrowserUrl || "#")}" style="color:${DB.textMute};">view in browser</a> ·
            <a class="dm-link" href="${esc(payload.archiveUrl || "#")}" style="color:${DB.textMute};">archive</a>
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
