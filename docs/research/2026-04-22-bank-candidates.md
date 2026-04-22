# Bank Candidates

This note tracks candidate test families for future expansion.

## Safe to Vendor First

### IPIP Mini-IPIP

- Family: trait profile
- Format: 20 Likert-style items
- Output: Big Five dimension scores
- License: public domain
- Source:
  - [IPIP permission page](https://ipip.ori.org/newPermission.htm)
  - [Mini-IPIP key](https://ipip.ori.org/MiniIPIPKey.htm)
- Status: already bundled as `mini-ipip-en`

### IPIP Big Five 50

- Family: trait profile
- Format: 50 Likert-style items
- Output: Big Five dimension scores
- License: public domain
- Source:
  - [IPIP home](https://ipip.ori.org/)
  - [50-item sample questionnaire](https://ipip.ori.org/new_ipip-50-item-scale.htm)
- Status: good next local bank if a longer English trait test is needed

## Researched, But Not Yet Vendored

### Open Jungian Type Scales (OJTS)

- Family: Jungian / MBTI-like
- Format: 48 questions
- Output: 16-type result across four dichotomies
- License signal: `CC BY-NC-SA 4.0`
- Source:
  - [OJTS](https://openpsychometrics.org/tests/OJTS/)
  - [OJTS development notes](https://openpsychometrics.org/tests/OJTS/development/)
- Release note: useful as a website adapter or external-bank candidate, but not the first choice for GPL bundling

### Open Extended Jungian Type Scales (OEJTS)

- Family: Jungian / MBTI-like
- Format: 32 paired questions
- Output: 16-type result
- License signal: `CC BY-NC-SA 4.0`
- Source:
  - [OEJTS PDF](https://openpsychometrics.org/tests/OJTS/development/OEJTS1.2.pdf)
  - [openjung/core](https://github.com/openjung/core)
- Release note: good scoring reference, but upstream question content still needs license review before vendoring

### OSPP Four Temperaments Test

- Family: archetype
- Format: 24 questions
- Output: four ranked temperaments
- License signal: `CC BY-NC-SA 4.0`
- Source:
  - [Open Psychometrics home](https://openpsychometrics.org/)
  - [O4TS development](https://openpsychometrics.org/tests/O4TS/development/)
- Release note: good candidate for a future `category_ranking` report mode

### Open Enneagram of Personality Scales

- Family: archetype
- Format: 54 questions
- Output: nine ranked enneagram styles
- License signal: verify before vendoring
- Source:
  - [OEPS](https://openpsychometrics.org/tests/OEPS/)
- Release note: strong entertainment value and structured output

### Open DISC Assessment Test

- Family: archetype
- Format: 16 questions
- Output: DISC ranking
- License signal: verify before vendoring
- Source:
  - [ODAT](https://openpsychometrics.org/tests/ODAT/)
- Release note: short and easy to stage, but confirm license before bundling

### Holland Code / RIASEC

- Family: career-fit
- Format: category rating
- Output: six Holland categories
- License signal: verify exact reuse path before vendoring
- Source:
  - [Open Psychometrics home](https://openpsychometrics.org/)
  - [My Next Move license note](https://www.mynextmove.org/help/license/)
- Release note: good way to expand beyond personality-style labels

## Future Schema Extensions

- `pair_letters`
  - already implemented
  - best for MBTI-like tests
- `dimension_scores`
  - already implemented
  - best for Big Five-style banks
- `category_ranking`
  - recommended for Enneagram, Four Temperaments, DISC, and RIASEC
- `nearest_profile_match`
  - recommended for character-match or profile-nearest-neighbor tests
