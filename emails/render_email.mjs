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

// One size uses one line-height and one gap. Large type is 1.25; kickers are 1.4; everything else is 1.5.
const type = {
  displayLh: "1.25",
  textLh: "1.5",
  kickerLh: "1.4",
  kickerTrack: "1.2px",
  afterHero: "0 0 16px",
  afterHeadline: "0 0 12px",
  afterSignoff: "0 0 8px",
  afterBody: "0 0 12px",
  afterItem: "0 0 16px",
  afterGroup: "0 0 16px",
  afterTldr: "0 0 8px",
  afterKicker: "0 0 12px",
  stack: "8px",
  quickSection: "8px 36px 16px",
};

const supportLines = (lines) =>
  lines
    .map((line, index) => {
      const margin = index === lines.length - 1 ? "0" : `0 0 ${type.stack}`;
      return `<div style="margin:${margin};line-height:${type.textLh};">${line}</div>`;
    })
    .join("");

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

const renderClusterLine = (story) => {
  const cluster = story && story.cluster;
  if (!cluster || typeof cluster !== "object") {
    return "";
  }
  const count = Number(cluster.badge_count || 0);
  if (count < 2 && !cluster.is_update) {
    return "";
  }
  let label = cluster.is_update && count < 2 ? "Update" : `Covered by ${count} sources`;
  if (cluster.is_update && count > 1) {
    label = `Update · ${label}`;
  }
  const also = (cluster.sources || [])
    .slice(1)
    .map((source) => {
      const name = esc(source.source || "Source");
      const url = esc(source.url || "#");
      return `<a class="dm-link" href="${url}" style="color:${DB.accent};">${name}</a>`;
    })
    .join(" · ");
  const conflicts = (cluster.conflicts || []).map((line) => esc(line)).join(" ");
  const lines = [esc(label)];
  if (also) {
    lines.push(`Also covered by ${also}`);
  }
  if (conflicts) {
    lines.push(`Where coverage differs: ${conflicts}`);
  }
  return `
      <mj-text css-class="dm-accent" color="${DB.accent}" font-size="13px" line-height="${type.textLh}" padding="${type.afterGroup}">
        ${supportLines(lines)}
      </mj-text>`;
};

const tldrItems = stories
  .map(
    (story, idx) => `
      <mj-text css-class="dm-dim" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.textDim}" font-size="12px" line-height="${type.textLh}" padding="${type.afterTldr}">
        ${String(idx + 1).padStart(2, "0")} · <span class="dm-text" style="color:${DB.text};">${esc(story.headline || "Untitled story")}</span>${story.read ? ` · ${esc(story.read)}` : ""}
      </mj-text>
    `
  )
  .join("");

const storyItems = stories
  .map(
    (story, idx) => `
      <mj-text css-class="dm-dim" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.textDim}" font-size="11px" line-height="${type.kickerLh}" text-transform="uppercase" letter-spacing="${type.kickerTrack}" padding="${type.afterKicker}">
        <span class="dm-chip" style="background:${DB.accent};color:${DB.accentInk};padding:2px 7px;border-radius:2px;font-weight:700;">${esc(story.tag || "Story")}</span>
        &nbsp;&nbsp;${String(idx + 1).padStart(2, "0")} · ${esc(story.source || "Source")} ${story.read ? `· ${esc(story.read)}` : ""}
      </mj-text>
      ${
        story.imageUrl
          ? `<mj-image src="${esc(story.imageUrl)}" alt="${esc(story.headline || "Story image")}" padding="${type.afterHeadline}" fluid-on-mobile="true" />`
          : ""
      }
      <mj-text css-class="dm-text" color="${DB.text}" font-size="24px" font-weight="700" line-height="${type.displayLh}" padding="${type.afterHeadline}" letter-spacing="-0.6px">
        ${esc(story.headline || "Untitled story")}
      </mj-text>
      <mj-text css-class="dm-mute" color="${DB.textMute}" font-size="15px" line-height="${type.textLh}" padding="${type.afterBody}">
        ${esc(story.summary || "No summary available.")}
      </mj-text>
      ${renderClusterLine(story)}
      <mj-table padding="${type.afterGroup}">
        <tr>
          <td class="dm-text" style="border-left:2px solid ${DB.accent};padding-left:12px;font-family:'JetBrains Mono', Menlo, monospace;color:${DB.text};font-size:13px;line-height:${type.textLh};">
            <span class="dm-accent" style="display:block;color:${DB.accent};text-transform:uppercase;letter-spacing:${type.kickerTrack};font-size:11px;font-weight:700;line-height:${type.kickerLh};margin-bottom:${type.stack};">Why it matters</span>
            ${esc(story.why || "Follow the source for details.")}
          </td>
        </tr>
      </mj-table>
      <mj-text font-family="'JetBrains Mono', Menlo, monospace" font-size="13px" line-height="${type.textLh}" padding="${type.afterGroup}">
        <a class="dm-link" href="${esc(story.url || "#")}" style="color:${DB.accent};text-decoration:underline;">→ read at ${esc((story.source || "source").toLowerCase())}</a>
      </mj-text>
      <mj-divider border-color="${DB.borderSoft}" />
    `
  )
  .join("");

const renderQuickHitSection = (title, items, padding) => {
  const rendered = (items || [])
    .map((item) => {
      const follow = (text) =>
        `<div style="margin:${type.stack} 0 0;font-size:13px;line-height:${type.textLh};">${text}</div>`;
      const summary = item.summary ? follow(esc(item.summary)) : "";
      const meaning = item.meaning
        ? follow(`What this means for people leading change: ${esc(item.meaning)}`)
        : "";
      const count = Number(item.cluster && item.cluster.badge_count) || 0;
      const covered = count > 1 ? follow(`Covered by ${count} sources`) : "";
      return `
      <mj-text css-class="dm-mute" color="${DB.textMute}" font-size="15px" line-height="${type.textLh}" padding="${type.afterItem}">
        <span style="color:${DB.accent};font-family:'JetBrains Mono', Menlo, monospace;">»</span> ${renderQuickHitHeadline(item)}${summary}${meaning}${covered}
      </mj-text>`;
    })
    .join("");
  if (!rendered.trim()) {
    return "";
  }
  return `<mj-section padding="${padding}">
        <mj-column>
          <mj-text css-class="dm-accent" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="11px" line-height="${type.kickerLh}" text-transform="uppercase" letter-spacing="${type.kickerTrack}" font-weight="700" padding="${type.afterKicker}">
            ◆ ${esc(title)}
          </mj-text>
          ${rendered}
        </mj-column>
      </mj-section>`;
};

const tweetSection = renderQuickHitSection(
  "Here's what's going on in Twitter/X",
  tweetHeadlines,
  type.quickSection
);
const communitySection = renderQuickHitSection(
  "Here's what we're hearing from the community",
  communityHeadlines,
  type.quickSection
);
const extraQuickHitSections = (payload.quickHitSections || [])
  .map((section) =>
    renderQuickHitSection(section.title || "More", section.items || [], type.quickSection)
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
      <mj-section background-color="${DB.bgRaised}" padding="30px 36px 0" border-bottom="1px solid ${DB.borderSoft}" css-class="dm-raised">
        <mj-column>
          <mj-table padding="0 0 16px">
            <tr>
              <td style="width:28px;vertical-align:middle;">
                <div class="dm-chip" style="width:28px;height:28px;background:${DB.accent};color:${DB.accentInk};text-align:center;line-height:28px;border-radius:2px;font-family:'JetBrains Mono',Menlo,monospace;font-size:14px;font-weight:800;">◼</div>
              </td>
              <td style="vertical-align:middle;padding-left:10px;">
                <div class="dm-text" style="font-family:Inter,Arial,sans-serif;color:${DB.text};font-size:15px;line-height:${type.textLh};font-weight:700;">AI News Daily</div>
              </td>
              <td style="vertical-align:middle;text-align:right;">
                <div class="dm-dim" style="font-family:'JetBrains Mono',Menlo,monospace;color:${DB.textDim};font-size:11px;line-height:${type.kickerLh};letter-spacing:${type.kickerTrack};text-transform:uppercase;">${esc(payload.subject || `ISSUE ${issueLabel} · ${stories.length} STORIES · 11 MIN READ`)}</div>
              </td>
            </tr>
          </mj-table>
          <mj-text css-class="dm-text" color="${DB.text}" font-size="36px" font-weight="700" line-height="${type.displayLh}" letter-spacing="-1.5px" padding="${type.afterHero}">
            ${esc(heroHeadline)}
          </mj-text>
          <mj-text css-class="dm-mute" color="${DB.textMute}" font-size="15px" line-height="${type.textLh}" padding="${type.afterBody}">
            ${esc(payload.intro || "")}
          </mj-text>
        </mj-column>
      </mj-section>
      <mj-section background-color="${DB.bgRaised}" padding="24px 36px" border-bottom="1px solid ${DB.borderSoft}" css-class="dm-raised">
        <mj-column>
          <mj-text css-class="dm-accent" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="11px" line-height="${type.kickerLh}" text-transform="uppercase" letter-spacing="${type.kickerTrack}" font-weight="700" padding="${type.afterKicker}">
            ◆ TL;DR
          </mj-text>
          ${tldrItems}
        </mj-column>
      </mj-section>
      <mj-section padding="24px 36px 8px">
        <mj-column>
          ${storyItems}
        </mj-column>
      </mj-section>
      ${tweetSection}
      ${communitySection}
      ${extraQuickHitSections}
      <mj-section background-color="${DB.bgRaised}" padding="28px 36px" border-top="1px solid ${DB.border}" css-class="dm-raised">
        <mj-column>
          <mj-text css-class="dm-accent" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.accent}" font-size="11px" line-height="${type.kickerLh}" text-transform="uppercase" letter-spacing="${type.kickerTrack}" font-weight="700" padding="${type.afterKicker}">
            ◆ End of edition
          </mj-text>
          <mj-text css-class="dm-text" color="${DB.text}" font-size="20px" font-weight="700" line-height="${type.displayLh}" letter-spacing="-0.4px" padding="${type.afterSignoff}">See you tomorrow.</mj-text>
          <mj-text css-class="dm-mute" color="${DB.textMute}" font-size="13px" line-height="${type.textLh}" padding="${type.afterGroup}">Got a tip? Just reply — a human reads every one.</mj-text>
          <mj-button css-class="dm-button" background-color="${DB.accent}" color="${DB.accentInk}" font-family="'JetBrains Mono', Menlo, monospace" font-size="12px" font-weight="700" text-transform="uppercase" letter-spacing="${type.kickerTrack}" inner-padding="10px 16px" border-radius="2px" href="${esc(payload.forwardUrl || payload.archiveUrl || "#")}">
            Forward to a friend →
          </mj-button>
        </mj-column>
      </mj-section>
      <mj-section padding="16px 36px 24px" border-top="1px solid ${DB.borderSoft}">
        <mj-column>
          <mj-text css-class="dm-dim" font-family="'JetBrains Mono', Menlo, monospace" color="${DB.textDim}" font-size="12px" line-height="${type.textLh}">
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
