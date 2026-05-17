# Deck — soutenance

25-slide Marp deck, target runtime **25 minutes** including a Q&A bumper.

## Render

```powershell
# PDF (for printing / sending the jury beforehand)
npx @marp-team/marp-cli docs/deck/soutenance.md -o docs/deck/soutenance.pdf

# HTML (for presenting in a browser, full-screen)
npx @marp-team/marp-cli docs/deck/soutenance.md -o docs/deck/soutenance.html

# Or watch-mode while editing:
npx @marp-team/marp-cli --watch docs/deck/soutenance.md
```

Marp picks up the front-matter (`marp: true`, theme, paginate, size). If
Marp isn't installed locally:

```powershell
npm install -g @marp-team/marp-cli
```

## Dry-run

The slide notes (HTML comments under each `## title`) are the script. Each
slide has a target second-budget written in the note. Time a full pass with
a stopwatch:

```
Slide 1   30s   (lead)
Slides 2-7   ~60s each   (problem + thesis + dataset + stack + arch + surfaces)
Slide 8   live demo cue (~3 min total, slides 9-13 cover what the demo shows)
Slides 14-21   60-75s each   (discipline, ML, infra, security, tests)
Slides 22-24   30-45s each   (scope, ADRs, roadmap, DoD)
Slide 25   Q&A bumper
```

**Hard cap: 25 minutes.** If the trial pass goes over 25 min, cut slide 17
(text-to-SQL safety) — it's the slide most safely subsumed into a Q&A
answer.

## Speaker notes

Comments under each `##` heading in `soutenance.md` are the speaker
script. Marp ignores them in the rendered output. Keep them short — they
should fit in your head, not be read off a screen.

## Replacements before recording / presenting

- `YOUR-LOOM-ID` → real Loom share id
- `YOUR-PUBLIC-URL` → public URL (AWS ALB DNS or Render or Vercel)
- `../img/hero.png` → real screenshot of the dashboard with OTIF dip framed

## Backup of the demo

If the live URL is dead at presentation time, the **Loom is the backup**.
Have it open in a tab before the talk starts. Slide 8 says "DEMO" — if
the URL doesn't load in 3 seconds, switch tabs to the Loom. Do not
apologize on camera.
