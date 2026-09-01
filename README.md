# EBL v0.9.4 — Genesis Launch UI

Full UI overhaul for the Genesis closed-alpha experience.

Main navigation:
- HOME — player, team, next game, EBL ticker, recent performance, EBL chat, team chat
- PLAYER — detailed stats tabs, XP pool, attribute development, contract/free agency, Legacy preview
- LEAGUE — divisional standings + games back + schedule
- ANALYTICS — league environment and leaderboards
- AWARDS — MVP, batting, pitching, stolen-base and fielding races
- GAMECAST — watch completed game event logs
- ADMIN — commissioner tools and developer Simulation Lab

Genesis uses six five-team divisions:
Atlantic, North, Central, South, West, Pacific.

Chat is stored server-side for EBL and team channels. This closed-alpha implementation still needs production moderation, mute/block/report UI, rate limiting, CSRF protection, persistent sessions, and HTTPS before public internet launch.

Run: python server.py
Open: http://127.0.0.1:8000


## v0.9.5 Player Builder update
Position-player rookie allocation is now separated into:
- HITTING
- FIELDING
- BASERUNNING

Pitcher rookie allocation is separated into:
- PITCHING
- FIELDING

The builder continuously shows the 50 XP starting pool, XP remaining, and XP spent.


## v0.9.6 EBL brand integration
- Added the official EBL crest to the header and login/landing experience.
- Rethemed the site around the logo palette: deep navy, red, silver, and white.
- Added stronger red league accents to navigation, ticker, divisions, and key cards.
- Kept the dark mobile-first visual style while making the entire product feel like one sports brand.


## v0.9.7 Character Creator
Player creation is now a four-step flow:
1. Basic Info
2. Appearance
3. Attributes
4. Review

Appearance includes 10 generic face presets and 10 generic hairstyle presets. These choices are cosmetic only and persist with the player profile.


## v0.9.8 Coach Interface
Human coach/owner accounts now have a Franchise Operations tab with:
- contract offers and open-offer management
- batting order
- fielding-position layout
- five-man starting rotation
- bullpen role assignments
- closer
- two setup roles
- middle relief and long relief groups
- defensive shift presets
- vs-LHB / vs-RHB plans
- corners-in and infield-in toggles

Genesis can remain CPU-controlled until franchises are handed to humans, but the human takeover interface is now in place.


## v0.9.9 Depth Chart & Substitution System
Coach interface now includes:
- positional depth chart for C, 1B, 2B, 3B, SS, LF, CF, RF, DH
- ranked pinch-hit order
- ranked pinch-run order
- defensive replacement order
- backup catcher designation
- late-inning defensive replacement inning
- pinch-hit aggressiveness
- steal aggressiveness
- bunt aggressiveness
- emergency bullpen group
- persistent strategy storage per franchise

These settings are stored now so the gameplay engine can consume them as substitution logic is deepened.


## v1.0 Coach Strategy Engine
Stored coach settings now affect game simulation:
- closer, setup, middle-relief, long-relief, and emergency bullpen usage
- late-inning pitching changes
- pinch-hitter usage
- pinch-runner usage
- defensive shift presets
- bunt aggression
- steal aggression
- late-inning defensive replacement windows
- strategy events appear in GameCast and are stored in the game box/event log

This is the first build where coach decisions directly change simulated game behavior.


## v1.0.1 EBL Newsroom & Community Story Layer
- Added a persistent league Newsroom.
- Simulated games automatically create result stories.
- Close games, blowouts, and strategy-heavy games receive contextual headlines.
- Home dashboard now shows the five newest EBL headlines.
- Dedicated News tab supports Games, Dugout, Transactions, and Milestones categories.
- News is generated from actual league events rather than scripted storylines.
- Genesis Day 0 begins with an intentionally empty newsroom: the league creates its own history.

## v1.0.2 Living League
- Persistent franchise rivalry tracking and intensity.
- Close/repeated matchups naturally build rivalry heat.
- Rivalry headlines are generated from league history.
- Genesis Record Book added.
- New records automatically create Newsroom stories.
- Community tab now includes Rivalry Board and Record Book.
- Weekly recap infrastructure added for seven-day storytelling.


## v1.0.3 Rivalry XP + Private Messages
- Rivalry games now grant a small performance-XP multiplier.
- Base rivalry boost starts at +2%.
- Historic/high-intensity rivalries scale gradually, capped at +8%.
- Salary XP is never boosted; only game-performance XP is affected.
- Added persistent private direct messages between users.
- Coaches, players, and commissioners can message individual users.
- DM threads are private to the two participants.
- Message length capped at 500 characters.


## v1.0.6 Accounts & Franchise Branding
- Account registration remains available from the landing page.
- Every new account now receives a one-time recovery code.
- Password recovery works with username + recovery code + new password.
- Successful recovery rotates to a new recovery code.
- Coach interface now includes Team Branding.
- Human coaches can set team display name, one of 10 generic logo styles, primary/secondary/accent colors, and home/away uniform palettes.
- Branding persists with the franchise and is independent of the coach account, so ownership can change without erasing team history.
- Logo creation is generic/preset for closed alpha; uploaded/custom artwork can be added for the finished product.
