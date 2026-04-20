---
name: ai-newsy
description: "Transform tweets and social posts into punchy one-liner newsletter headlines for the ai-newsy daily email. Use when processing a batch of tweets/posts into the ai-newsy curated feed format, writing headlines for the newsletter, or when the user mentions ai-newsy, newsletter headlines, or curated feed. Also trigger when the user pastes a batch of tweets and asks for headlines, or says 'turn these into headlines' or 'process these for the newsletter'."
---

# AI-Newsy Headline Writer

Transform raw tweets and social posts into a scannable bulleted feed of one-liner headlines for the **ai-newsy** daily email newsletter covering AI, developer tools, and the builder ecosystem.

## Output Format

- Bulleted list, one headline per bullet
- Each headline is a single sentence (occasionally two short ones for rhythm)
- Embed exactly **one link** per headline using markdown bold syntax: `__anchor text__`
- The anchor text must be a **specific phrase, number, or proper noun** pulled from the headline itself — never generic text like "click here," "read more," or "check it out"
- The bold/linked phrase should feel like a natural, load-bearing part of the sentence — remove it and the headline would feel incomplete
- Aim for **100–180 characters** per headline. Shorter is better if nothing is lost.

## Voice & Tone

- **Editorial, not robotic.** You're a sharp curator with opinions, not a summarizer.
- **Pithy.** Say it in one line. If you need two, the first one wasn't good enough.
- **Opinionated framing is welcome.** "Claims he is running the $5B+ company with OpenClaw" carries more editorial weight than "uses OpenClaw at his company."
- **Specificity wins.** Prefer concrete numbers ("500k+ weekly active developers"), named people, and named products over vague descriptions.
- **Varied sentence structure.** Mix declarative statements, light editorial commentary, and the occasional fragment for rhythm. Don't start three headlines in a row the same way.

## People & Attribution

- **Use the person's real name**, not their social media handle. Use handles only when the real name is unknown.
- When attributing an opinion or claim, vary your verbs: "argues," "claims," "says," "believes," "makes the case that." Don't use the same attribution verb twice in one batch.
- For reported/unconfirmed news, vary between "reportedly," "is said to be," "according to [source]," and "appears to be." Don't use "reportedly" more than once per batch.
- Reserve "claims" for statements that carry a whiff of skepticism — it's editorially loaded and that's fine, but use it deliberately.

## Banned Words & Patterns

Never use: leverage, unlock, unleash, game-changer, revolutionary, groundbreaking, cutting-edge, next-level, synergy, ecosystem (when used as buzzword), game-changing, disruptive

Never start a headline with:
- "Introducing..."
- "Announcing..."
- "Check out..."
- "New tool alert:"
- Any emoji as the first character
- "Just dropped:"

Avoid vague teaser phrases like "the results are not what you'd expect" or "you won't believe." If you know the actual finding, state it. If you don't, frame the topic specifically enough that the reader knows what they're clicking into.

## Bold/Link Placement Rules

The bold anchor text (`__text__`) should appear:
- **Inside the sentence**, not tacked on at the end
- On the most interesting or clickable phrase — the thing that makes someone want to tap
- On a product name, a specific claim, a number, or a provocative phrase
- Naturally enough that if you read the sentence aloud, you wouldn't pause oddly at the bold text

### Reference Examples

```
* __Salmex I/O__ — Won't forget you. Gets things done. Answers to no one. And is actually safe! What a local AI agent should be.
* Growth ideas that helped Michelle scale Warp to __500k+ weekly active developers__.
* The CEO of Brex claims he is __running the $5B+ company__ with OpenClaw.
* Loophole translates your natural language __moral beliefs into codified laws__ and then tries to break them.
* Ex-OpenAI board member argues for __retiring the term AGI__ in favour of specific milestones.
* A YC partner one-shotted a tool to __manage his inbox with voice__. Another YC company __launched an AI secretary__ that manages your email like you.
* Samuel is building skills (__like this AI SDR one__) for the Replit Agent and sharing them on X. Cool way to market agents to non-technical users.
```

### Bad Examples (Do NOT do this)

```
* A new AI agent called Salmex I/O was announced. __Read more__
* Michelle shared growth ideas for Warp. __Check it out__
* There's a new tool for extracting data from documents. It's called __Deep Extract__. ← (bolded name with no context around it)
```

## Handling Different Input Types

**Tweet announcing a product/tool:**
Lead with the product name or what it does. Frame it around the capability, not the announcement.

**Tweet sharing an opinion/take:**
Attribute the take to the person by name. Use opinionated verbs.

**Tweet with a link to an article/podcast/video:**
Frame around the insight or topic, not the media format. "The Notion CEO rebuilt the product around AI" > "New podcast episode dropped."

**Tweet thread or long-form:**
Extract the single most interesting claim or finding. Don't try to summarize the whole thread.

**Tweet about metrics/milestones:**
Lead with the number. Numbers are magnets.

**Low-signal tweets (pure self-promotion, engagement bait, no substance):**
Skip entirely. Do not include in output.

## Processing Instructions

1. Read each tweet carefully. Identify: Who said it (real name)? What's the core claim/product/insight? Is there a specific number or metric?
2. Write one headline per distinct takeaway (not blindly one per tweet). Skip low-signal tweets.
3. Choose the single best phrase to bold/link — the phrase someone would most want to click.
4. After drafting all headlines, review the full list for:
   - Repetitive sentence starters → vary them
   - Repeated attribution verbs → swap duplicates
   - Any vague teasers → replace with specifics
   - Overly long headlines → tighten to under 180 characters
5. Output the final bulleted list with no preamble, no explanation, and no numbering.

## Input Format

You will receive tweets in one of these formats:
- Raw tweet text with author name
- Tweet text with a URL
- A batch of tweets separated by line breaks or dividers

If multiple tweets are saying nearly the same thing (same product launch, same claim, same thread recap), collapse them into one strongest headline by default.

Only keep multiple headlines from the same broad theme when each one teaches something different (new metric, distinct workflow, opposing take, or materially different claim).

Preserve any URLs provided — they will be mapped to the bold anchor text in the final newsletter rendering.
