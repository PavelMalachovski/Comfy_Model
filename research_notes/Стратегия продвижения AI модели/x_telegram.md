# X (Twitter) and Telegram for an AI-generated adult-adjacent persona: rules, growth, monetization, and the funnel to Fanvue (as of 2026-11-21)

*Source-quality labels used below: [OFFICIAL] = platform's own docs or code; [PRESS] = news outlets; [LEGAL] = law-firm or regulator material; [DATA] = third-party dataset analysis; [VENDOR] = agency, tool, or course blog with a commercial stake; [ANECDOTAL] = forum or practitioner self-reports; [OLD] = dated before 2025, may be outdated. X Help Center pages returned HTTP 403 to direct fetches, so X policy wording comes from search-indexed copies of those pages. Treat it as accurate to the indexed version, not guaranteed to be the live text.*

---

## 1. X: adult content policy, sensitive-media visibility, UK/EU age verification, and synthetic/AI media rules

### Takeaway
X explicitly allows consensually produced adult nudity and sexual content when it is labeled as sensitive and kept off highly visible surfaces: profile photo, header, live video, List banners, and Community covers. Minors and users with no birth date on file can't open it. Since late July 2025, users in the UK, Ireland, and the EU who haven't passed X's age assurance are blocked from 18+ media. Adult-flagged authors are filtered out of part of X's out-of-network recommendation pipeline (confirmed in the open-sourced 2026 code). As of Nov 2026, X has **no general mandatory AI-disclosure rule** for creators. Its synthetic-media policy targets deceptive or harmful media, and the 2026 additions are narrow: a "manipulated media" label, and an AI-label requirement for monetized armed-conflict videos. However, regulators (Ofcom, EU) have been actively pursuing X over AI sexual imagery since the January 2026 Grok scandal, so enforcement pressure on AI nudity is high.

### Cited Findings

#### Adult content policy (core rules)
- [OFFICIAL] "You may share consensually produced and distributed adult nudity or sexual behavior, provided it's properly labeled and not prominently displayed." — [X Help: Adult content](https://help.x.com/rules-and-policies/adult-content). The newest dated snapshot that surfaced was May 2024; check the live page.
- [PRESS][OLD] X formally changed its rules to allow consensual adult content in June 2024 — [The Hill](https://thehill.com/policy/technology/4700638-x-twitter-porn-policy-update/); [Fortune](https://fortune.com/2024/06/03/does-x-allow-nudes-elon-musk-twitter-x-social-media-meta-instagram-facebook-onlyfans/)
- [OFFICIAL] "You can't include Adult Content within areas that are highly visible on X, including in live video, profile pictures, headers, List banners, or Community cover photos." — [X Help: Adult content](https://help.x.com/rules-and-policies/adult-content)
- [OFFICIAL] Labeling works at account level or per post. The account setting "Mark media you post as containing material that may be sensitive" puts all of an account's media behind a warning. A one-time content warning can also be added to individual posts, categorized as Nudity, Violence, or Sensitive. — [X Help: Your media settings](https://help.x.com/en/rules-and-policies/media-settings)
- [OFFICIAL] Users under 18, and viewers with no birth date on their profile, cannot click through to view marked content — [X Help: Media policy / Adult content](https://help.x.com/en/rules-and-policies/media-policy)
- [OFFICIAL] X "may also use automated techniques to detect and label potentially sensitive media, and to detect and label accounts that frequently post potentially sensitive media." If an account repeatedly mislabels content, X may switch on the account-level sensitive setting itself and apply an account label. Visitors to a labeled profile may see an interstitial asking whether they still want to view it. Users who opted in to sensitive content skip the interstitial. — [X Help: Your media settings](https://help.x.com/en/rules-and-policies/media-settings)
- [OFFICIAL] If a profile or header image violates the rules, X "may temporarily suspend your account and remove the offending content. Repeat violations will result in a permanent suspension." The account may also be locked until the media is removed. — [X Help: Media policy](https://help.x.com/en/rules-and-policies/media-policy)
- [PRESS][OLD] In March 2024, X confirmed that Community admins can set an "Adult Content" label on a Community to keep its posts from showing to some users. At the time, X's leadership was pitching Communities as key to growth. — [TechCrunch, 2024-03-28](https://techcrunch.com/2024/03/28/x-is-testing-nsfw-adult-communities-according-to-screenshots/)

#### How sensitive content is distributed (For You, search)
- [OFFICIAL] X open-sourced its Grok-based For You ranking code in January 2026 — [TechCrunch, 2026-01-20](https://techcrunch.com/2026/01/20/x-open-sources-its-algorithm-while-facing-a-transparency-fine-and-grok-controversies/). The repository README, current through at least late Oct 2026, describes:
  - a pre-scoring filter, `OONNsfwSimclustersFilter`, that removes out-of-network SimClusters candidates from authors flagged for adult content when the viewer doesn't follow the author;
  - a visibility-filtering service that returns ALLOW / NOTICE / INTERSTITIAL / DROP. INTERSTITIAL is described as "behind an interstitial the viewer can tap through, e.g. for adult or graphic media". It reads labels from classifiers ("Grox": spam, adult, violent media), block/mute/follow status, and the viewer's settings and country;
  - some rules that apply only to out-of-network recommendations: "The same post is allowed to a follower."

  Source: [GitHub: xai-org/x-algorithm](https://github.com/xai-org/x-algorithm)
- [PRESS][OLD] In October 2023, X began flagging NSFW posts as sensitive and restricting flagged accounts' reach. Sex workers reported their engagement collapsed and their accounts disappeared from X search, often without notice. — [TechCrunch, 2023-10-13](https://techcrunch.com/2023/10/13/sex-work-x-premium-subscription-twitter-blue-nudity-porn-ban/). Creators also received the notice "We've added a label to your account which may impact its reach" — [404 Media](https://www.404media.co/twitter-x-sensitive-content-label-advertisers/)
- [OFFICIAL] X's own terms-of-service filing to the New York AG lists "Excluding the post from search results, trends, and recommended notifications" among its post-level restrictions — [X Corp. NY AG policy report, 2025 Q3](https://ag.ny.gov/sites/default/files/social-media-policy-report/2025-q3-x-corp-policy.pdf)
- [ANECDOTAL] An advocacy petition alleges ongoing shadowbanning and search-banning of NSFW accounts without notification or appeal. This is advocacy, not evidence. — [Change.org](https://www.change.org/p/end-twitter-x-s-shadowbanning-and-searchbanning-of-nsfw-accounts)

#### Age assurance (UK, Ireland, EU)
- [PRESS] X introduced age-assurance measures around 26 July 2025, citing the UK Online Safety Act, Ireland's Online Safety Code (in force 21 July 2025), and the EU DSA. Ofcom required services hosting porn to deploy "highly effective" age assurance by 25 July 2025. — [RTÉ, 2025-07-28](https://www.rte.ie/news/business/2025/0728/1525685-x-introduces-age-assurance-measures-to-meet-regulations); [X Help: Age assurance](https://help.x.com/en/rules-and-policies/age-assurance); [Bloomberg, 2025-04-23](https://www.bloomberg.com/news/articles/2025-04-23/uk-s-new-child-safety-rules-set-to-challenge-porn-posts-on-x)
- [PRESS] Users who haven't verified their age either don't see 18+ content in their timeline or see "Due to local laws, we are temporarily restricting access to this content until X estimates your age." Methods include age estimation, self-attested age, and ID verification. — [Tom's Guide](https://www.tomsguide.com/computing/vpns/age-verification-comes-to-x-and-you-might-not-be-able-to-do-it-at-all)
- [PRESS] There are reports, not confirmed, that user-initiated ID verification is effectively tied to X Premium — [PPC Land](https://ppc.land/x-implements-age-verification-system-behind-premium-paywall/). X has also updated its EU age verification and temporarily blocked some content there (date and details not verified) — [Agence Europe](https://agenceurope.eu/en/bulletin/article/13690/8/x-updates-its-age-verification-system-in-eu-and-temporarily-blocks-access-to-certain-content)

#### Grok scandal and regulator pressure (2026)
- [LEGAL/OFFICIAL] On 12 Jan 2026, Ofcom opened a formal Online Safety Act investigation into X. It followed reports that Grok was used to generate and share content that may amount to intimate-image abuse, CSAM, and pornography accessible to children. The scope includes how fast X removes illegal content and how effective its age assurance is. — [Ofcom announcement](https://www.ofcom.org.uk/online-safety/illegal-and-harmful-content/ofcom-launches-investigation-into-x-over-grok-sexualised-imagery). The case page was last updated 14 Oct 2026 and the investigation is still open — [Ofcom case page](https://www.ofcom.org.uk/online-safety/illegal-and-harmful-content/investigation-into-x-internet-unlimited-company-and-its-compliance-with-duties-to-protect-its-users-from-illegal-content-and-child-users-from-harmful-content)
- [PRESS] X first limited Grok's "undressing" edits to paying users. It later restricted image editing for subscribers too, and by mid-January said it had blocked Grok from creating intimate images of real people. — [The Register, 2026-01-12](https://www.theregister.com/2026/01/12/xai_grok_uk_regulation/); [Ofcom](https://www.ofcom.org.uk/online-safety/illegal-and-harmful-content/ofcom-launches-investigation-into-x-over-grok-sexualised-imagery)

#### Synthetic / AI media policy and labels
- [OFFICIAL][OLD-dated] X's Synthetic and Manipulated Media policy, last dated April 2023, lets X label or remove misleading media likely to cause harm. Repeated sharing of harmful misleading media can lead to reduced visibility, locks, or suspension. — [X Help: Synthetic and manipulated media](https://help.twitter.com/en/rules-and-policies/manipulated-media)
- [PRESS] In January 2026, Musk announced a "manipulated media" label for edited or fake images. Enforcement looks inconsistent: a manipulated White House photo went unlabeled. — [TechCrunch, 2026-01-28](https://techcrunch.com/2026/01/28/elon-musk-teases-a-new-image-labeling-system-for-xwe-think); [PetaPixel, 2026-01-29](https://petapixel.com/2026/01/29/elon-musk-announces-mainipulated-media-label-on-x-images)
- [PRESS] In March 2026, X said monetized creators who post AI-generated "armed conflict" videos without disclosure lose Creator Revenue Sharing for 90 days, and repeat offenders face permanent removal. Enforcement uses detection tools, AI metadata, and Community Notes. AI content outside conflict footage, including "deceptive influencer content", is **not** covered. X is separately testing a broader user-applied AI-label toggle with no timeline. — [Engadget](https://www.engadget.com/social-media/x-to-require-ai-labels-on-armed-conflict-videos-from-paid-creators-citing-times-of-war-183631400.html); [eWeek](https://www.eweek.com/news/x-suspends-creators-unlabeled-ai-war-videos/); [heise](https://heise.de/-11199447)

### Inferences
- **Account setup for the persona's X account:** keep the avatar and header strictly SFW; a yoga or pilates portrait fits the brand. Switch on the account-level "sensitive media" setting from day one, because the account will carry lingerie and implied teasers. That avoids "mislabeling" strikes and forced labels. Never post adult media in live video or Community cover images.
- **Distribution ceiling:** once the account is flagged for adult content (labeling makes this near-certain), the open-source code shows it loses SimClusters out-of-network recommendations to non-followers, and its media sits behind interstitials. Growth will therefore depend on in-network engagement, replies, reposts and quotes by others, Communities, and off-platform cross-promotion. It's unknown whether the Grok-based Phoenix retrieval path also suppresses adult-flagged authors.
- **SFW top-of-funnel on X:** the fitness, flexibility, and mature-lifestyle niche can produce fully SFW content (stretch flows, pilates technique, Dubai lifestyle) that is eligible for normal For You distribution. That argues for either (a) a SFW-heavy main account that uses only occasional, sparingly labeled teasers, or (b) a separate SFW "fitness" account alongside the labeled teaser account, with clearly distinct content. Duplicate content across accounts violates the authenticity rules (see Section 4).
- **UK/EU reach haircut:** sensitive-labeled media is invisible to UK, Irish, and EU users who haven't passed age assurance. Plan on audiences elsewhere (US, Gulf, Asia) for teaser reach. Unlabeled SFW posts are unaffected.
- **AI disclosure:** X doesn't require it in general. Still, Fanvue requires AI disclosure (Section 9), EU AI Act Article 50 transparency duties apply from 2 Aug 2026 (Section 7), and Community Notes and "deception" reports are a reputational risk. Taken together, a short bio disclosure ("AI-generated / virtual model") is the low-risk default, and it keeps the persona consistent across platforms.
- **AI nudity scrutiny:** after the Grok scandal, X's classifiers and trust-and-safety teams are under regulator scrutiny for AI sexual imagery. Content must never resemble a real person or look youthful. The persona's stated age of 40 and mature styling lower the age-appearance risk.

### Gaps
- The live X Help pages (403) couldn't be read in full, and it's unconfirmed whether the adult-content policy text changed in 2025–2026.
- The weights in `home-mixer/params/param.rs` aren't in the README, and it's unknown whether Phoenix retrieval excludes adult-flagged authors.
- No official 2025–2026 X statement says whether adult-flagged accounts are excluded from search autocomplete or results for opted-in users.
- X's non-consensual nudity policy wording on AI-generated images, and any US state age-verification effects on X, weren't researched.

---

## 2. X: growth tactics for NSFW/adult creators in 2025–2026, with compliance and risk for each

### Takeaway
The 2026 ranker predicts likes, replies, reposts, quotes, and shares; clicks (post, profile, link, photo expand, video open); dwell time and video watch time; follows; and negative actions (not interested, mute, block, report). It spreads exposure across authors and boosts new low-impression authors. Adult-flagged accounts lose part of their out-of-network reach, so NSFW teaser accounts grow mainly through in-network engagement, replies under relevant accounts, Communities, and cross-promotion. X Premium correlates with about 10x median reach, and Premium replies rank higher. X Ads can't promote adult content, and X's own monetization (Subscriptions, revenue sharing) excludes adult/sexual content. Follow trains, "decks", paid engagement, follow churn, and duplicate multi-account posting break X's manipulation rules, though enforcement is uneven.

### Cited Findings

#### What the algorithm rewards (primary source)
- [OFFICIAL] Phoenix predicts the probability of these actions:
  - engagement: "favorite · reply · repost · quote · share"
  - clicks: "post · profile · link · photo expand · video open"
  - attention: "dwell time", "video continuation seconds"
  - author follows
  - negatives: "not interested", "mute author", "block author", "report", "not dwelled"

  The final score is "Σ (weight_i × P(action_i))". Author diversity applies: "each post after an author's first is multiplied by a decaying factor, down to a floor". There is an out-of-network discount, plus a boost for new authors whose impressions are below a threshold. The README doesn't mention Premium or verified boosts. — [GitHub: xai-org/x-algorithm](https://github.com/xai-org/x-algorithm)

#### X Premium
- [DATA] Buffer analyzed 18.8M posts from about 71k accounts, Aug 2024–Aug 2025 (published 2 Oct 2025).
  - Median impressions per post: under 100 for regular accounts, about 600 for Premium, over 1,550 for Premium+, which is roughly 10x for Premium.
  - Median engagement: regular accounts fell to 0% by March 2025; the Premium tiers sit at about 0.49–0.55%.
  - Overall median reach fell from about 1,000 to under 750 over the year.

  Source: [Buffer](https://buffer.com/resources/x-premium-review/)
- [VENDOR] Sprout Social says Premium users' replies are algorithmically prioritized to the top of conversation threads — [Sprout Social](https://sproutsocial.com/insights/twitter-algorithm/). Circleboom dissents, arguing Premium mainly improves presentation rather than ranking — [Circleboom](https://circleboom.com/blog/does-x-premium-boost-algorithm/)

#### Practitioner playbooks [VENDOR/ANECDOTAL]
- SirenCY, an OnlyFans agency, published a guide on 2 Apr 2026, reviewed May 2026. All of its numbers are unsourced, and it contradicts itself in places. Its recommendations, by area:
  - **Cadence:** 3–5 posts a day (its FAQ says 5–8), with at least one daily.
  - **Content mix:** about 40% NSFW previews, 30% personal, 20% engagement, 10% promotional. It claims 4-image posts "perform better".
  - **Hashtags:** 1–3 per post, rotating 10–15 tags. It flags #OnlyFans, #OF, #porn, #nsfw, #sex, #sexy, and #hot as high-risk, and prefers niche, community, attribute, and location tags.
  - **Links:** link in bio and in the pinned post, with a direct link in about 1 of every 3–4 posts. Update the pinned post weekly.
  - **Engagement:** reply to every comment within 60 minutes and engage with 20–30 accounts a day. Small engagement pods of 5–10 are "allowed" in its view, with a warning that X detects artificial engagement.
  - **Outreach:** a weekly Spaces session, plus S4S threads and outreach to 5–10 creators.
  - **DMs and tools:** DM only followers who have engaged repeatedly; no mass DMs. Scheduling tools are fine, but automating engagement isn't.

  Source: [SirenCY](https://www.sirency.com/blog/onlyfans-twitter-x-marketing-guide-2026)

#### Engagement groups, follow trains, decks (rules and enforcement)
- [OFFICIAL] The Platform Manipulation policy page (dated April 2025) bans "follow churn" (mass follow/unfollow to inflate counts) and duplicating another account's followers, especially via automation — [X Help: Platform manipulation](https://help.x.com/rules-and-policies/platform-manipulation). X's developer guidelines say services shouldn't compensate people to take actions on X, because that creates inauthentic engagement — [X Developer guidelines](https://docs.x.com/developer-guidelines)
- [DATA][OLD] A 2020 study describes follow trains as a "direct violation" of Twitter's platform manipulation and spam policy — [arXiv 2010.13691](https://arxiv.org/abs/2010.13691v2). A 2024 study found enforcement weak: only 6.3% of follow-back accounts were suspended over two years — [arXiv 2403.15856](https://arxiv.org/html/2403.15856v1)
- [PRESS][OLD] Twitter acted against sellers of paid "decks" (TweetDeck setups for mass-retweeting buyers' posts) after a BuzzFeed investigation. Removing multi-account retweeting made decks largely useless. — [Techdirt](https://www.techdirt.com/tag/buying-engagement/)

#### X Ads (paid acquisition on X)
- [OFFICIAL] "X prohibits the promotion of adult sexual content globally." Sex toys are allowed only with prior authorization and 21+ targeting, and dating services need pre-approval. — [X Ads policy: Adult sexual products and services](https://business.x.com/en/help/ads-policies/ads-content-policies/adult-or-sexual-products-and-services). The update log notes sexual merchandise ads are permitted with restrictions in Brazil, France, Germany, Mexico, and the UK (entry date not verified) — [X Ads policy update log](https://business.x.com/en/help/ads-policies/ads-policy-update-log)
- [DATA] An academic audit found about 38% of sampled ads violated Twitter's adult-content ad policy, and only about 63% of those were removed. The data predates 2025. — [arXiv 2309.12591](https://web3.arxiv.org/pdf/2309.12591)

#### X's own monetization (not usable for adult content)
- [OFFICIAL] X's Creator Monetization Standards list Adult or Sexual Content as restricted. Adult entertainment, erotica, and pornography sites are not eligible for monetization. — [X Help: Creator Monetization Standards](https://help.x.com/en/rules-and-policies/content-monetization-standards); [X Help: Content monetization policy](https://help.x.com/en/rules-and-policies/content-monetization-policy)
- [OFFICIAL] Subscriptions require the account to be 3+ months old, have 2,000+ active followers, and hold Premium, and all Subscriptions content must meet the monetization standards — [X Help: Subscriptions policy](https://help.x.com/en/rules-and-policies/subscriptions-policy). Creator Revenue Sharing closed to new enrollment on 7 Aug 2026 and was due to close on 7 Sep 2026, moving to an "Original Content Rewards Program" (from search-indexed help text; verify) — [X Help: Creator revenue sharing](https://help.x.com/using-x/creator-revenue-sharing)
- [PRESS] X announced a "creator era" with a sponsored-content marketplace on 19 May 2026. Nothing in the coverage addresses adult creators. — [Tubefilter](https://www.tubefilter.com/?p=192389)

### Inferences

#### Tactic-by-tactic compliance and risk matrix (X)
| Tactic | Complies with X rules? | Ban / reach risk | Reputation risk | Notes for this persona |
|---|---|---|---|---|
| 3–5 posts/day mixing SFW fitness content and labeled teasers | Yes | Low | Low | Author-diversity decay means posting more brings diminishing returns per post. |
| Short vertical video (stretch flows, splits, pilates reformer) | Yes | Low | Low | "Video continuation seconds" and dwell are predicted signals. Natural fit for the flexibility niche. |
| Multi-image posts (sets of 2–4) | Yes | Low | Low | "Photo expand" is a predicted click action. |
| Labeled teasers (lingerie/implied) on the teaser account | Yes, if labeled | Medium if left unlabeled | Low | Unlabeled adult media brings strikes and forced labels. Avatar and header must stay SFW. |
| Replying under large accounts (fitness, mature-women, lifestyle) | Yes, if substantive | Medium if repetitive or carrying links (spam) | Medium (seen as "reply-guy spam") | Premium replies rank higher. Mutes, blocks, and reports are negative signals. |
| 1–3 niche hashtags | Yes | Low | Low | Avoid explicit hashtags. Hashtag stuffing reads as spam. |
| Pinned post with offer/teaser and a link | Yes | Low | Low | Media must be labeled. |
| X Communities (fitness/yoga; adult-labeled Communities for teasers) | Yes, within each Community's rules | Low–Medium | Low | Community covers can't contain adult content. |
| Organic SFS / shoutout exchanges with other creators | Grey: occasional mutual promotion isn't named in X's rules | Medium if systematic | Medium (spammy partners) | Partner only with clean, AI-labeled accounts. |
| Retweet/engagement groups, pods, Telegram "RT groups", "decks" | No (platform manipulation / inauthentic engagement) | High | Medium–High | Detection risk. Weak enforcement doesn't make it safe. |
| Follow trains, follow-for-follow, follow churn | No | High | Medium | Explicitly banned (follow churn). |
| Buying followers or engagement | No | High | High | It also corrupts conversion data. |
| Paid shoutouts from large promo accounts | Not addressed by the sources found; likely allowed if it isn't engagement-for-pay | Medium (fake-follower promo accounts) | Medium | Test with tracked links and pay per result where possible. Disclosure rules weren't verified (see Gaps). |
| X Premium | Yes | Low | Low | Probably improves reach and reply ranking (Buffer: about 10x median reach). Cheap relative to the likely benefit. |
| X Ads promoting the adult funnel | No | High (ad account ban) | Medium | Global prohibition. |
| Scheduling via official tools or API | Yes | Low | Low | Fine. |
| Auto-like, auto-follow, auto-DM, or scripted browser automation | No | High (non-API automation → permanent suspension possible) | Medium | Avoid. |
| Mass cold DMs | No (unsolicited/spam) | High | High | Only reply to inbound DMs. |
| X Subscriptions or revenue sharing for adult content | No | Medium (loss of monetization) | Low | Monetize off-platform only. |

- **Premium:** Buffer's 10x reach gap is correlational, since Premium accounts are also more active and invested, and the open-source README doesn't show an explicit Premium multiplier. Even so, multiple sources agree that Premium replies get priority. For a reply-driven growth strategy, Premium is the cheapest lever.
- **Content strategy implied by the signals:** the niche suits watch-time-heavy SFW video (flexibility "how far can she go" clips, morning routines in a Dubai Marina setting) and photo sets that invite expands. Save explicit-adjacent material for labeled posts and keep the rest SFW so the account's overall negative-signal rate stays low.

### Gaps
- No reliable 2025–2026 data on video vs. photo performance for adult-flagged accounts, or on optimal cadence (only vendor opinions).
- Paid shoutouts: pricing, effectiveness, and how X's paid-partnership disclosure rules apply weren't found.
- Unclear whether the Community "Adult Content" label (tested in 2024) still works the same way in 2026.
- No source quantifies how much Premium helps specifically for sensitive-labeled accounts.

---

## 3. X: are posts with external links downranked in 2025–2026, and what's the best practice?

### Takeaway
The evidence conflicts. X leadership says links are not deboosted: Nikita Bier in Oct 2025, and Bier plus Musk in July 2026 ("We haven't for over a year"). The open-source ranker treats a link click as a *positive* predicted action and documents no link penalty. Against that, Buffer's data shows link posts from non-Premium accounts had a median 0% engagement from March 2025 onward, and Musk said in 2025 that ranking optimizes for time spent on X. The practical consensus is that link posts underperform because they pull users off-platform and generate fewer on-platform signals. Premium narrows the gap. For adult funnels, keep links in the bio and pinned post, and post native media with a CTA.

### Cited Findings
- [PRESS] In 2025, Musk appeared to confirm link deprioritization: the algorithm optimizes for time spent, so off-platform links get boosted less — [Cybernews](https://cybernews.com/news/musk-x-posts-with-links-suppression/); [Benton Institute](https://www.benton.org/headlines/musk-admits-x-throttles-links-%E2%80%98news-influencers%E2%80%99-take-over)
- [PRESS] In October 2025, Bier posted "Links are not deboosted". He attributed lower reach to users not liking or replying after opening a link, and stated a goal of equal timeline visibility for all content. — [Roboin, 2025-10-20](https://roboin.io/article/en/2025/10/20/x-product-chief-denies-rumor-that-link-posts-are-deboosted/)
- [PRESS] Also in October 2025, X tested an iOS in-app browser that keeps like, reply, and repost buttons visible while users view external pages — [Nieman Lab](https://www.niemanlab.org/2025/10/x-makes-overtures-to-journalists-with-new-feature-designed-to-improve-reach-for-links/); [TechSpot](https://www.techspot.com/news/109943-x-tests-new-way-keep-users-engaged-when.html)
- [PRESS] In July 2026, Bier told Mark Zuckerberg he no longer needs to put links in replies, and Musk replied "We haven't for over a year." — [Free Press Journal](https://freepressjournal.in/tech/x-product-head-nikita-bier-confirms-link-penalty-removed-over-a-year-ago-tells-mark-zuckerberg-he-can-post-them-directly)
- [DATA] For regular (non-Premium) accounts, link posts were "completely suppressed since March 2025", with a median engagement of 0%. Premium users' link posts still underperform text, video, and images, at about 0.25–0.3% engagement. Buffer recommends Premium+ for link sharing. The data covers Aug 2024–Aug 2025. — [Buffer](https://buffer.com/resources/x-premium-review/)
- [OFFICIAL] The ranker lists "link" among predicted click actions, and the README describes no special handling of external links — [GitHub: xai-org/x-algorithm](https://github.com/xai-org/x-algorithm)
- [VENDOR] Some 2026 guides still assert a link penalty without evidence — [SocialPilot](https://socialpilot.co/blog/twitter-algorithm). Agency practice is a link in the bio and pinned post, plus a direct link in about 1 of every 3–4 posts — [SirenCY](https://www.sirency.com/blog/onlyfans-twitter-x-marketing-guide-2026)

### Inferences
- **Best practice for this funnel:**
  - Put the primary CTA in the bio and pinned post, ideally the Telegram channel or a single Fanvue tracking link.
  - Post native media (video, photo sets) with no link, plus a text CTA such as "full set on my Telegram" or "link in bio".
  - Add a link in a self-reply only after the main post has gathered engagement.
  - Never post the same link post repeatedly, because duplicate posts/links are a spam signal.
  - All of this is low risk and compliant.
- **Measuring:** use separate Fanvue tracking links and separate Telegram invite links per source (X bio, X pinned post, X replies). Then the link-penalty debate matters less than measured click-through.
- **Premium** is the strongest available mitigation if links are posted in the main post.

### Gaps
- No independent 2026 measurement after the July 2026 "no penalty" statements, and Buffer's data ends Aug 2025.
- Unknown whether X attaches warnings or extra friction to links pointing at adult domains (Fanvue) via t.co.

---

## 4. X: suspension and visibility-restriction risks (automation, spam, multiple accounts, sensitive flags, location transparency)

### Takeaway
The main ways an AI adult-teaser account gets restricted on X:
1. Unlabeled sensitive media, or adult imagery in the avatar, header, or live video.
2. Platform manipulation: follow churn, follow trains, paid engagement, duplicate content across several accounts, and suspension evasion.
3. Non-API automation such as browser scripting (permanent suspension possible), automated unsolicited DMs, and bulk following.
4. Heavy negative feedback (mutes, blocks, reports).

A newer exposure risk dates from Nov 2025: the "About this account" panel shows the country an account is based in. That can contradict the persona's "lives in Dubai" story if the operator is elsewhere.

### Cited Findings
- [OFFICIAL] Automated activity that violates the automation rules can lead to enforcement, including suspension. Using "non-API-based forms of automation, such as scripting the X website… may result in the permanent suspension of your account." — [X Help: Automation rules](https://help.x.com/en/rules-and-policies/x-automation)
- [OFFICIAL] You may not post "duplicative or substantially similar posts on one account or over multiple accounts you operate." The rules apply to automated posting, DMs, and following/unfollowing, and prohibit spamming users or sending unsolicited messages. — [X Help: Automation rules](https://help.x.com/en/rules-and-policies/x-automation). The developer guidelines say never perform "bulk, aggressive, or spammy actions, including bulk following" — [X Developer platform usage guidelines](https://developer.x.com/en/developer-terms/policy/platform-usage-guidelines)
- [OFFICIAL] Multiple accounts are allowed when each serves a distinct purpose (e.g., brand accounts per language or location). Operating multiple accounts that post substantially similar content isn't allowed, though cross-posting in another language is. Creating accounts to evade a suspension is prohibited, and X may suspend other accounts it believes belong to the same holder. — [X Help: Automation rules](https://help.x.com/en/rules-and-policies/x-automation); [X Help: Authenticity](https://help.x.com/bn/rules-and-policies/authenticity.html)
- [OFFICIAL] The Platform Manipulation policy (dated April 2025) bans follow churn and the duplication of follower lists — [X Help: Platform manipulation](https://help.x.com/rules-and-policies/platform-manipulation)
- [OFFICIAL] Sensitive flags: X auto-detects sensitive media and labels accounts that post it often, and repeated mislabeling triggers a forced account setting and label — [X Help: Your media settings](https://help.x.com/en/rules-and-policies/media-settings). An adult image in the profile or header leads to a temporary suspension or lock, and repeat violations to a permanent suspension — [X Help: Media policy](https://help.x.com/en/rules-and-policies/media-policy)
- [PRESS] "About this account" (late Nov 2025): tapping an account's join date shows the country or region where it's based. In countries with punitive speech laws, holders can show only the region. The feature exposed many accounts that posed as US-based but were run from abroad. — [Axios, 2025-11-24](https://axios.com/2025/11/24/x-location-feature-foreign-political-accounts); [Outlook Business](https://www.outlookbusiness.com/deeptech/tech/x-rolls-out-about-this-account-feature-exposes-foreign-accounts-sparks-privacy-alarm); [The Week](https://theweek.com/politics/x-location-update-exposes-international-troll-industry). X admitted errors and removed registration-country data for older accounts ("not 100% for old accounts"), and some labels were plainly wrong — [The Star](https://www.thestar.com.my/tech/tech-news/2025/11/29/the-039rough-edges039-of-xs-new-feature-have-sewn-chaos-and-confusion)
- [VENDOR/ANECDOTAL] Shadowban triggers practitioners cite:
  - hashtag overuse;
  - duplicate tweets or links;
  - rapid follow/unfollow;
  - excessive mentions;
  - mass reporting;
  - bought followers or follow-for-follow.

  Recovery advice: stop automation, delete violating posts, take a 48-hour break, and appeal if the restriction lasts beyond 7 days. — [SirenCY](https://www.sirency.com/blog/onlyfans-twitter-x-marketing-guide-2026)

### Inferences
- **Location mismatch risk:** if the X account is operated from a country other than the UAE, "About this account" will likely show that country. For a persona whose story is "a 40-year-old trainer living in Dubai", that invites "catfish/fake" call-outs, Community Notes, and reports. Since the persona is AI-generated, the cleanest mitigation is an explicit "AI-generated / virtual model" bio disclosure (also required on Fanvue). Masking location with a VPN could itself be read as deceptive, and its detection wasn't verified.
- **Operating model:** run one labeled teaser account, optionally plus one SFW fitness account with distinct, non-duplicate content. Use official schedulers only. Don't use RT groups, decks, follow trains, or auto-DMs. Keep a backup of the content and the audience (Telegram and Fanvue) in case of suspension, because suspension evasion with new accounts is itself a violation.

### Gaps
- Exact enforcement thresholds, appeal success rates, and how often adult-flagged accounts are suspended are unknown.
- Unknown whether X marks VPN or proxy use in the location label.
- The live Platform Manipulation page text (403) wasn't read, so it's unconfirmed whether it explicitly names engagement pods or "Retweet for Retweet".

---

## 5. Telegram: role in AI-model funnels and native monetization (Stars paid media, Star subscriptions, paid DMs and suggested posts, third-party bots, Telegram Ads, cross-promo, catalogs)

### Takeaway
Telegram is the "warm middle" of AI-model funnels. A free public channel carries teasers and announcements. A private layer can be monetized natively with Telegram Stars through:
- paid photo/video posts;
- monthly Star subscriptions sold via invite links to private channels (fixed 30-day period);
- Star reactions;
- paid DMs and suggested posts to channels (July 2025).

Telegram's creator terms pay about **US$0.013 per Star**, withdrawable via Fragment as crypto after a **21-day hold**. Buyers pay about $0.02 per Star in-app, so creators keep roughly 65% of buyer spend before conversion costs. Telegram Ads ban nudity and sexually suggestive content, including in what's being promoted, and dating, so adult funnels can't use Telegram's native ads.

### Cited Findings

#### Native monetization primitives
- [OFFICIAL] Paid media: creators can gate photos and videos (the only supported types) behind a Stars price, visible after payment. Stars can be withdrawn via the "Gram" cryptocurrency or spent on ads for the channel "with next to 0 commission". Earlier docs and coverage name the crypto Toncoin/TON via Fragment. — [Telegram API: Paid media](https://core.telegram.org/api/paid-media); [TechCrunch, 2024-07-03](https://techcrunch.com/2024/07/03/telegram-lets-creators-share-paid-content-to-channels) [OLD launch date]
- [OFFICIAL] Star subscriptions:
  - Paid invite links work only for **private** channels.
  - "the only allowed subscription period is 30*24*60*60" (30 days).
  - The maximum price is set by the `stars_subscription_amount_max` config value; the docs show no number.
  - Users are added automatically after paying, and the subscription auto-renews.
  - Users can cancel. If they leave while the subscription is active, they can rejoin without paying again.

  Source: [Telegram API: Star subscriptions](https://core.telegram.org/api/subscriptions)
- [OFFICIAL/PRESS] In Aug 2024, Telegram announced Star subscriptions as a Patreon-like way to monetize extra or early-access content. Creators receive 100% of Stars from Star reactions. — [Telegram blog: Super Channels, Star Reactions and Subscriptions](https://telegram.org/blog/superchannels-star-reactions-subscriptions); [afaqs](https://www.afaqs.com/news/digital/telegram-introduces-paid-subscriptions-and-star-reactions-to-enhance-creator-revenue) [OLD launch date]
- [OFFICIAL] Telegram's Terms of Service for Content Creators:
  - Owners receive "an equivalent of 0.013 USD worth of rewards" for each Star earned from paid posts (§2.2).
  - Eligible channels get a 50% share of ad revenue (§2.1).
  - Stars spent on ads for the same channel are valued at $0.02 each (§4.3).
  - "Star balance rewards require 21 days" before withdrawal; Gram balances need 2 days (§4.1).
  - Stars expire after 3 years (§4.7).
  - Withdrawals are "neither reversible nor refundable" (§4.5).
  - Buyers keep access to unlocked posts even if the post or channel is deleted (§2.2.1).
  - Telegram takes "reasonable technical precautions" against redistribution but can't eliminate it (§2.2.1).
  - Invalid activity, including abuse of "third-party refund systems", lets Telegram withhold or debit rewards even after withdrawal (§5.1).

  Source: [Telegram ToS for Content Creators](https://telegram.org/tos/content-creator-rewards)
- [OFFICIAL] Channel DMs and suggested posts (July 2025): subscribers can message a channel directly and suggest posts with a Stars or Toncoin payment attached. The owner can counter-offer on text, media, or price. Payment is released 24 hours after posting and refunded if the post is removed earlier. Stars bought through app stores can be refunded; Toncoin payments can't. — [Telegram blog: Checklists, Suggested Posts and More Monetization Options for Channels](https://telegram.org/blog/checklists-suggested-posts). The API lets a channel set a Stars price for direct messages — [Telegram API: Channel direct messages (monoforum)](https://core.telegram.org/api/monoforum)
- [OFFICIAL] Telegram also shipped "Star Messages" (paid messages); details weren't verified in this research — [Telegram blog: Star Messages, Pinned Gifts, Verification Platform 2.0](https://www.telegram.org/blog/star-messages-gateway-2-0-and-more)

#### Telegram Ads (native paid acquisition) rules
- [OFFICIAL] Ads must not promote "graphic, shocking, or sexual content, products and services". The examples given include "Nudity, sexually explicit and sexually suggestive content", "excessively exposed intimate body parts", sexual merchandise, sexual entertainment, and "dating services" (§5.1). Rules for the destination:
  - "Destinations must match the ad text."
  - "Concealing or replacing the content of the destination to pass the ad review" is prohibited (§4.4).
  - Channels need a post within the two weeks before review (§4.5).
  - Channels need a profile image and description (§4.1).

  AI-generated content isn't mentioned. — [Telegram Ad Platform guidelines](https://ads.telegram.org/guidelines)
- [VENDOR] Changing the destination after approval can lead to suspension — [Adsgram blog](https://adsgram.ai/blog/adsgram/telegram-ads-requirements-moderation-restrictions-and-examples). Yandex, which resells Telegram channel ads, also refuses adult content and advises against images of women with exposed body parts — [Yandex Direct: Telegram ads special rules](https://yandex.com/support/direct/en/telegram-ads/features)

#### Discovery and cross-promotion infrastructure
- [OFFICIAL] "Similar channels" (late 2023): after joining a channel, users see similar public channels chosen by subscriber-base overlap. The list is also reachable from the channel profile. — [Telegram blog: Similar Channels](https://telegram.org/blog/similar-channels); [Telegram API: Similar channels](https://core.telegram.org/api/recommend). Telegram's bug tracker shows recommendations aren't restricted to public channels — [Telegram bug tracker](https://bugs.telegram.org/c/49699)
- [VENDOR] The catalogs TGStat and Telemetrio auto-index public channels, and submitting directly speeds up indexing. Cross-promo means swapping posts or story mentions with 5–10 similar-size channels. — [Unilink 2026 playbook](https://unil.ink/blog/how-to-grow-telegram-channel-2026); [CompanionLink, Aug 2026](https://www.companionlink.com/blog/2026/08/how-to-grow-a-telegram-channel-in-2026-a-step-by-step-guide/)

#### Tools used by adult/AI operators
- [VENDOR] OnlyChatAI automates fan chats and PPV sales across OnlyFans and Telegram, with Stars unlocking paid photos — [AlternativeTo: OnlyChatAI](https://alternativeto.net/software/onlychatai/about/)
- [ANECDOTAL] A BlackHatWorld operator journal ("The Million Dollar AI Girlfriend: 2 Years Into the Build | OFM + Telegram Stars") argues that Stars let the conversation and the purchase happen in the same place. The fetch was blocked, so only snippets were seen. — [BlackHatWorld](https://www.blackhatworld.com/posts/21207765/)

### Inferences
- **Recommended Telegram architecture for the persona:**
  1. A **public free channel** that stays SFW to suggestive at most: fitness clips, lingerie or implied teasers, set announcements, polls. That keeps it clear of the ToS rule on illegal porn in public channels and of App Store filtering (Section 6).
  2. A **private Star-subscription channel** or **paid-media posts** for low-ticket impulse buys, such as previews of the Fanvue sets.
  3. **Fanvue as the main paid hub** for full lingerie, implied, and nude sets, plus DMs.

  Use channel DMs with a Stars price to filter time-wasters and monetize chat. Use suggested posts sparingly, since fan-submitted content in an AI-persona channel is off-brand.
- **Telegram Ads aren't viable** for the adult teaser channel: suggestive creatives and adult destinations are prohibited, and swapping content after approval is a violation. The only compliant use would be a genuinely SFW fitness channel whose content matches the ad and stays that way.
- **Stars earned can only be recycled into Telegram Ads** for the same channel. Given the ad rules, that's of limited value for an adult-adjacent channel.

### Gaps
- Current values of `stars_subscription_amount_max` and the paid-post price ceiling weren't found.
- The adult-content policies and fees of third-party subscription bots (InviteMember, Tribute, and others) weren't found. Searches returned nothing usable.
- Unknown whether "similar channels" recommends 18+ channels, and how catalogs (TGStat/Telemetrio) treat adult channels.

---

## 6. Telegram: adult content policy, app-store builds, takedowns, and regulatory pressure

### Takeaway
Telegram's ToS bans only "illegal pornographic content on publicly viewable" channels and bots. Legal adult content in private channels and chats isn't addressed. In practice:
- App Store builds hide content flagged as violating Apple's guidelines.
- Moderation pressure rose sharply in 2026. Apple pulled Telegram from the App Store worldwide for a day (3–4 Aug 2026) over CSAM shared by one user. Telegram blocked about 338k groups and channels over CSAM in 2026. Ofcom has had an investigation open since April 2026, and Telegram offers optional facial age checks in the UK.
- Telegram purges AI "nudify" bots when the press flags them.

So expect report-driven takedowns of anything explicit and public. Keep the public channel non-explicit.

### Cited Findings
- [OFFICIAL] Users agree not to "Post illegal pornographic content on publicly viewable Telegram channels, bots, etc." and not to "Use our service to send spam or scam users". Private chats aren't addressed, and no updated date is shown. — [Telegram Terms of Service](https://telegram.org/tos)
- [OFFICIAL] The creator terms defer to the general ToS for prohibited content and don't mention sexual or AI-generated content — [Telegram ToS for Content Creators](https://telegram.org/tos/content-creator-rewards)
- [PRESS] On 3–4 Aug 2026, Apple removed Telegram from the App Store worldwide after a user shared CSAM, and restored it the same day once the content was removed and the user banned. Telegram stayed on the Mac App Store and Google Play. Telegram said it had blocked nearly 338,000 groups and channels over such material that year. — [Al Jazeera, 2026-08-04](https://www.aljazeera.com/economy/2026/8/4/telegram-says-apple-suspension-followed-content-norms-violation-by-one-user); [9to5Mac, 2026-08-03](https://9to5mac.com/2026/08/03/telegram-appears-to-have-been-pulled-from-the-app-store-worldwide/); [iPhone in Canada](https://www.iphoneincanada.ca/2026/08/04/apple-briefly-pulls-telegram-from-app-store-over-content-violation/)
- [PRESS][OLD] Apple also pulled Telegram in 2018 over "inappropriate content". Apple's guidelines allow removal of apps used primarily for pornographic content. — [TechCrunch, 2018-02-01](https://techcrunch.com/2018/02/01/telegram-apps-fall-foul-of-ios-app-store-content-rules/)
- [VENDOR — low reliability] The App Store version of Telegram may hide content that violates store guidelines even where Telegram itself allows it, and the "sensitive content" filter toggle works differently by client — [PositionIsEverything guide](https://www.positioniseverything.net/how-to-disable-filtering-on-your-telegram-account/)
- [LEGAL/OFFICIAL] On 21 April 2026, Ofcom opened an investigation into whether Telegram meets its illegal-content (CSAM) duties under the Online Safety Act — [Ofcom case page](https://www.ofcom.org.uk/online-safety/illegal-and-harmful-content/investigation-into-the-provider-of-telegram-and-its-compliance-with-duties-to-protect-users-from-illegal-content-under-the-online-safety-act-2023); [The Next Web, 2026-04-21](https://thenextweb.com/news/ofcom-telegram-investigation-csam-online-safety-act). Al Jazeera notes Australia's online-safety regulator also fined Telegram for delayed answers on such material — [Al Jazeera](https://www.aljazeera.com/economy/2026/8/4/telegram-says-apple-suspension-followed-content-norms-violation-by-one-user)
- [PRESS] Telegram added optional on-device facial age estimation for UK users. Certain content is blurred or blocked if the check isn't completed, and Telegram may keep the result and metadata. — [Tom's Guide](https://www.tomsguide.com/computing/vpns/here-are-6-sites-requiring-age-verification-will-you-be-affected)
- [PRESS][OLD] In Oct 2024, WIRED found at least 50 Telegram "nudify" bots with more than 4M combined monthly users. Telegram deleted 75 bots and channels after WIRED's inquiry, and operators said they would rebuild. — [Malwarebytes summarizing WIRED](https://www.malwarebytes.com/blog/news/2024/10/nudify-deepfake-bots-remove-clothes-from-victims-in-minutes-and-millions-are-using-them). Deepfake bots are built to survive takedowns — [Centre for Information Resilience](https://www.info-res.org/cir/articles/telegram-deepfake-bots-are-built-to-survive-takedowns/)

### Inferences
- **The public teaser channel must stay non-explicit** (lingerie or implied at most), for three reasons:
  - the ToS bans illegal porn in public channels, and what counts as "illegal" depends on viewer jurisdiction;
  - iOS App Store builds may hide flagged content, and a large share of mobile buyers are on iOS;
  - public explicit content is the easiest target for reports and takedowns.

  Put nude content only behind a paywall, in a private Star-subscription channel or (preferably) on Fanvue.
- **AI sexual imagery is a hot regulatory category** on Telegram because of the nudify-bot problem. Ways to reduce risk:
  - make it obvious the persona is a fictional adult (40);
  - avoid any resemblance to real people;
  - label content as AI;
  - never offer "generate a nude of X" services.
- **Platform concentration risk:** Telegram could lose a channel, or face App Store friction again, with little notice. Treat Fanvue as the system of record for paying fans. Keep a backup Telegram channel and regularly push members to Fanvue and other owned channels.

### Gaps
- No official Telegram documentation on how the iOS/Google Play sensitive-content filtering currently works, or whether Google Play builds filter differently.
- No data on takedown rates for *legal* adult creator channels (public or private).
- Unknown how Telegram applies the "illegal pornography" test across jurisdictions, e.g., channels viewable from the UAE, where pornography is illegal. Not researched; flag for legal review.

---

## 7. Telegram: AI companion / "AI girlfriend" chatbots — how they work, monetization, rules, risks

### Takeaway
AI girlfriend bots on Telegram are LLM chat bots, sometimes with voice or image generation, that monetize through Telegram Stars. Typical models are per-message credits or monthly Star subscriptions (XTR invoices, 30-day period). Telegram positions Stars as the payment rail for digital goods in bots, for App Store compliance. Unit economics are small: a 750-Star monthly plan nets about $9.75. The legal and platform risks have grown:
- the companion-chatbot laws: California SB 243 (in effect since 1 Jan 2026) and New York's law;
- EU AI Act Article 50, in force from 2 Aug 2026, which requires disclosure of AI interaction and labeling of deepfakes;
- age-gating expectations;
- Telegram purges of sexual AI bots;
- refund and abuse exposure through the app stores.

### Cited Findings
- [OFFICIAL] Stars are Telegram's payment system for digital goods and services in bots and mini apps, designed to comply with Apple's and Google's digital-goods rules. Using Stars means accepting the Stars ToS. — [Telegram blog: Telegram Stars](https://telegram.org/blog/telegram-stars); [Telegram Stars ToS](https://telegram.org/tos/stars)
- [OFFICIAL] Bots sell subscriptions through XTR invoice links with `subscription_period` set to 30 days. Invoices must be exported as deep links, and "any number of subscriptions can be active for a given bot at the same time". — [Telegram API: Star subscriptions](https://core.telegram.org/api/subscriptions)
- [VENDOR] A developer tutorial charges 1 Star per request using XTR invoices — [DEV: GPT-5 Telegram bot with Stars monetization](https://dev.to/king_triton/building-a-gpt-5-telegram-bot-with-telegram-stars-monetization-5g7c). A paid-bot developer (May 2026) puts net revenue at about $1.95 a month on a 150-Star plan and about $9.75 on a 750-Star plan, at about $0.013 per Star — [DEV: What Telegram Stars actually pay](https://dev.to/__747bb5a1521/i-built-a-paid-telegram-bot-heres-what-telegram-stars-actually-pay-3fo)
- [ANECDOTAL] A freelancer portfolio describes a companion avatar bot ("Lyubava") built on Llama 3.3 70B via Groq, with ElevenLabs voice and Stars payments, deliberately designed with "inaccessibility" to feel like a personality — [Freelancehunt portfolio](https://freelancehunt.com/en/showcase/work/lyubava-bot/2035299.html)
- [VENDOR] OnlyChatAI automates fan chat and PPV across OnlyFans and Telegram — [AlternativeTo](https://alternativeto.net/software/onlychatai/about/). [ANECDOTAL] A BlackHatWorld AI-girlfriend operator journal says the conversion layer, turning a click into a paying chat, is where most operations stall. Self-reported. — [BlackHatWorld](https://www.blackhatworld.com/posts/21207765/)
- [LEGAL] California SB 243 (signed 13 Oct 2025, effective 1 Jan 2026):
  - operators must give a "clear and conspicuous" notice that the chatbot is AI wherever a reasonable person could be misled into thinking it's human;
  - a notice that it may be unsuitable for some minors;
  - three-hour reminders for users known to be minors;
  - a private right of action with damages of at least $1,000.

  Sources: [TechCrunch](https://techcrunch.com/2025/10/13/california-becomes-first-state-to-regulate-ai-companion-chatbots); [Skadden](https://skadden.com/insights/publications/2025/10/new-california-companion-chatbot-law). New York enacted a companion-AI law too — [Morrison Foerster](https://www.mofo.com/resources/insights/251120-new-york-and-california-enact-landmark-ai)
- [LEGAL] EU AI Act Article 50 has applied since 2 Aug 2026. It covers chatbot interaction disclosure, synthetic-media marking, and deepfake labeling, with fines up to €15M or 3% of worldwide turnover. The Digital Omnibus gives pre-existing generative systems until 2 Dec 2026 for the machine-readable marking duty under Article 50(2). Sources differ on whether 50(1) is affected. — [Goodwin](https://www.goodwinlaw.com/en/insights/publications/2026/08/alerts-technology-dpc-eu-ai-act-transparency-obligations-now-in-force); [Morgan Lewis](https://www.morganlewis.com/ru/blogs/sourcingatmorganlewis/2026/08/eu-ai-acts-transparency-rules-what-went-into-effect-on-2-august); [Ropes & Gray](https://www.ropesgray.com/en/insights/viewpoints/2026/08/102nfqm/you-talkin-to-me-operationalising-the-eu-ai-acts-transparency-obligations). Draft Commission guidance says content that looks or sounds like a real person must be labeled "even if no deception was intended" — [Greenberg Traurig, June 2026](https://www.gtlaw.com/es/insights/2026/6/deepfakes-chatbots-ai-generated-text-european-commission-details-transparency-obligations-under-the-ai-act)
- [PRESS][OLD] Telegram removed 75 nudify bots and channels after press inquiries — [Malwarebytes summarizing WIRED](https://www.malwarebytes.com/blog/news/2024/10/nudify-deepfake-bots-remove-clothes-from-victims-in-minutes-and-millions-are-using-them)

### Inferences
- **For this persona, a companion bot is a possible later upsell, not a launch priority.** It adds legal surface:
  - AI disclosure under SB 243 and Article 50;
  - a minor-safety notice and an age gate;
  - Stars-only payments with low unit revenue;
  - app-store refund abuse;
  - risk of becoming a nudify-style target if it generates images on demand.
- **A lower-risk path** is a Telegram bot used as a free "concierge": welcome message, schedule, link router to Fanvue, and FAQ. Monetize chat on Fanvue's paid DMs, where the platform-level AI tag already covers disclosure.
- **If a companion bot is built anyway:**
  - show "you are chatting with an AI character" at the start and periodically;
  - gate it at 18+;
  - keep chat to text and voice, with no on-demand nude image generation;
  - pre-render image unlocks only from the persona's own approved sets;
  - log consent and age confirmations.

### Gaps
- No reliable revenue or retention data for Telegram AI-companion bots (only self-reports).
- No Telegram-specific rules found for sexual AI chat bots, or for whether bots must age-verify.
- Unclear how SB 243 and Article 50 apply to a bot run by a non-US/non-EU operator serving users globally. Needs legal review.

---

## 8. Telegram: growing a channel from zero in 2025–2026, and converting X/IG/Threads traffic

### Takeaway
Telegram has no algorithmic feed. Native discovery comes from "similar channels" recommendations, search, and third-party catalogs (TGStat, Telemetrio). New channels therefore grow mostly from external traffic: link-in-bio from X, IG, and Threads, story CTAs, Reddit. Beyond that they grow through post-swap cross-promotion with similar-size channels and paid placements in other channels. Telegram Ads are off-limits for sexual or suggestive creatives. Vendor benchmarks are unverified:
- about $0.10–$1.00 per subscriber via paid placements;
- 50–500 subscribers in month one;
- cross-promo deals are hard to get below about 1,000 subscribers.

### Cited Findings
- [OFFICIAL] "Similar channels" appear when a user joins a channel, chosen by subscriber overlap — [Telegram blog](https://telegram.org/blog/similar-channels); [Telegram API](https://core.telegram.org/api/recommend)
- [VENDOR] 2025–2026 growth guides claim the following. Attribution of each number to a specific guide wasn't individually verified.
  - Cost per subscriber of about $0.10–$1.00 via paid ads or sponsored posts, depending on niche.
  - Telegram Ads at a minimum of roughly $0.5 or 1 TON per 1,000 views.
  - Cross-promo by contacting 5–10 similar-size channels and swapping pinned posts or story mentions.
  - A "credibility problem" in cross-promo negotiations below about 1,000 subscribers; most admins won't S4S with a 200-sub channel.
  - Catalog listing in TGStat and Telemetrio.
  - Benchmarks of 50–500 subscribers in month one and 2,500–10,000 by month six. Strong cross-promo or paid ads can reach 10K in 30–60 days.

  Sources: [Unilink 2026 playbook](https://unil.ink/blog/how-to-grow-telegram-channel-2026); [CompanionLink, Aug 2026](https://www.companionlink.com/blog/2026/08/how-to-grow-a-telegram-channel-in-2026-a-step-by-step-guide/); [Crescitaly](https://blog.crescitaly.com/how-to-grow-a-telegram-channel-strategies-that-work-in-2026/); [AirDroid](https://www.airdroid.com/ai-insights/telegram-subscribers-increase/)
- [OFFICIAL] Telegram Ads prohibit sexual or suggestive ads and dating, and require destinations to match the ad — [Telegram Ad Platform guidelines](https://ads.telegram.org/guidelines)
- [OFFICIAL] Telegram's ToS bans using the service "to send spam" — [Telegram ToS](https://telegram.org/tos)
- [DATA/VENDOR] AI creators typically post SFW content on Instagram or TikTok and drive fans to Fanvue through link-in-bio — [Sacra: Fanvue's link-in-bio conversion play](https://sacra.com/chat/h/5dbef429-beaa-4ddc-b0d6-8eb4444c7a7f/)

### Inferences

#### Tactic-by-tactic compliance and risk matrix (Telegram growth)
| Tactic | Complies? | Ban risk | Reputation risk | Notes |
|---|---|---|---|---|
| Telegram link in X bio and pinned post; CTA posts on X ("full set in TG") | Yes (X and Telegram) | Low | Low | Use a distinct invite link per source so joins can be attributed. |
| Telegram link from IG/Threads (bio or story link) | Telegram: yes. Meta: separate research (other researcher) | Unknown on the Meta side | Low | Keep the public channel SFW so Meta reviewers don't find adult content behind the link. |
| Cross-promo (post swaps) with similar AI-model or fitness channels | Yes (no Telegram rule against it) | Low | Medium if partners are spammy or explicit-public | Vet partners. Prefer AI-labeled, adult-only-behind-paywall partners. |
| Paid placements (shoutouts) in other channels | Yes (private deals) | Low | Medium (bought-bot audiences) | Pay per measured joins where possible, and check view-to-subscriber ratios before buying. |
| Listing in TGStat/Telemetrio catalogs | Yes | Low | Low | Their handling of 18+ categories is unknown. |
| Telegram Ads with suggestive creatives, or to an adult destination | No | High (ad rejection or suspension) | Low | Prohibited under §5.1 and §4.4. |
| Telegram Ads for a genuinely SFW fitness channel | Yes, if the destination matches and stays SFW | Medium if content later shifts | Low | Swapping content after approval is a violation. |
| Buying fake subscribers or bot members | Violates the spirit of the anti-spam ToS | Medium | High | Inflates vanity metrics and destroys conversion rates. |
| Mass-inviting or DM-spamming users with userbots | No (spam) | High (account bans) | High | Avoid. |
| Star giveaways or contests inside the channel | Not reviewed in this research | Unknown | Low | Verify against the Stars ToS. |

- **The X → Telegram hop is the weak link.** Telegram requires installing the app and joining, and a large share of X users may already have it. The CTA should promise something exclusive and concrete, e.g., "uncensored stretch session tonight, TG only", rather than a bare link.

### Gaps
- No reliable 2025–2026 data on conversion from X, IG, or Threads to Telegram joins (only vendor claims).
- A 31 July 2025 update reportedly added global search for public posts. It was seen only in a non-English summary of a Telegram update page and needs verifying.
- How catalogs and similar-channel recommendations treat 18+ channels is unknown.

---

## 9. Selling directly in Telegram vs. driving to Fanvue: fees, payout friction, buyer trust

### Takeaway
Per fan dollar, Fanvue pays more. Fanvue's standard split is 80/20, with temporary promotional uplifts for new creators. Funds sit in a 7-day pending period (extendable to 28), and payouts are initiated within about 10 business days to bank, crypto, or wallets. On Telegram, the creator gets about $0.013 per Star against about $0.02 retail. That's roughly 65% of buyer spend, before about 5% in Fragment fees and exchange costs, paid in crypto after a 21-day hold with a 1,000-Star minimum. Telegram wins on purchase friction: one-tap App Store or Google Play payment with no new account or card form. Fanvue wins on take rate, fiat payouts, a recognized AI-creator framework (the mandatory AI tag), chargeback rules, and a full creator toolset. Most operators would use Telegram for low-ticket impulse unlocks and community, and Fanvue for subscriptions and higher-ticket content.

### Cited Findings

#### Fanvue
- [OFFICIAL] "The standard Creator Earning Rate is 80% of gross revenue from Paid-for Services, with the remaining 20% retained by Fanvue as Platform Fees." Other terms:
  - A "Promotional Earning Rate", a temporary uplift for new creators, can be changed or withdrawn at Fanvue's discretion.
  - "The standard Pending Period is seven (7) days" and it "may be extended up to twenty-eight (28) days".
  - Fanvue aims to initiate payouts within 10 business days.
  - Payout methods are bank transfer, crypto wallets (where supported), and third-party wallets. Each method has its own minimum threshold.
  - If chargebacks or disputes exceed 1.5% in a rolling 30 days, Fanvue may charge a discretionary $50 fee per additional dispute.

  Source: [Fanvue: Creator Earnings & Payouts](https://legal.fanvue.com/creator-earnings-payouts). Per search snippets, the policy was last updated 21 Aug 2025.
- [VENDOR] Third-party sources describe the intro rate as 15% for the first 30 days, then 20% — [eCommerce Fastlane review](https://ecommercefastlane.com/fanvue-review/). A vendor estimates that withdrawal and FX costs on a $500 international wire can total $55–$170 (11–34%) — [Sozee](https://sozee.ai/resources/creator-revenue-sharing-fanvue-alternatives)
- [OFFICIAL] AI-generated content is allowed under Fanvue's T&C §10.3. Creators "must disclose that it is not real and was generated using AI", and "Every AI creator on Fanvue is marked with the relevant AI tag." — [Fanvue Help: Is AI content allowed](https://help.fanvue.com/en/articles/9538738-is-ai-content-allowed-on-fanvue); [Fanvue Help: How do I know if a creator is AI](https://help.fanvue.com/en/articles/14290142-how-do-i-know-if-a-creator-is-ai)
- [DATA/VENDOR] Sacra estimates fully AI creators were about 15% of Fanvue GMV by mid-2025, with top AI creators earning $10k–$20k+ a month — [Sacra: AI OnlyFans at $100M/year](https://sacra.com/research/ai-onlyfans-at-100m-year/); [Sacra: Fanvue at $65M ARR](https://sacra.com/research/fanvue-at-65m-arr/). OMR reported AI creators at 15% of Fanvue revenue in one month — [OMR](https://omr.com/en/daily/ai-models-fanvue)

#### Telegram Stars
- [OFFICIAL] Payouts are "an equivalent of 0.013 USD" per Star from paid posts. Stars are valued at $0.02 when spent on ads. There's a 21-day hold for Stars, and withdrawals are irreversible. Telegram can debit rewards for abuse of "third-party refund systems". — [Telegram ToS for Content Creators](https://telegram.org/tos/content-creator-rewards). The official USD sell rate is exposed in the `stars_usd_sell_rate_x1000` config — [Telegram API: Stars](https://core.telegram.org/api/stars)
- [OFFICIAL] Stars can be bought via in-app purchase in the iOS and Android apps, or via @PremiumBot in the direct-download Android build and in the Web and Desktop apps — [Telegram Stars ToS](https://telegram.org/tos/stars). Stars bought through app stores can be refunded via the stores; Toncoin payments can't — [Telegram blog: Suggested posts](https://telegram.org/blog/checklists-suggested-posts)
- [VENDOR] A paid-bot developer (May 2026) puts retail at about $0.02 per Star (75 Stars for $1.49), with Apple/Google taking 30%. The developer nets about $0.013 per Star, with a 1,000-Star minimum withdrawal and a 21-day delay. Payout comes in TON, which then has to go through an exchange with its own KYC and fees. — [DEV: What Telegram Stars actually pay](https://dev.to/__747bb5a1521/i-built-a-paid-telegram-bot-heres-what-telegram-stars-actually-pay-3fo)
- [VENDOR — conflicts with official framing] A promotional withdrawal guide (June 2026) claims a fixed rate of "200 Stars = 1 TON", so the USD value floats with the TON price. It cites about a 5% Fragment fee, 0.1% for the TON/USDT trade, free SEPA, and $15–30 for SWIFT. — [starsearn on DEV](https://dev.to/starsearn/how-telegram-creators-cash-out-stars-the-complete-2026-withdrawal-guide-dko). A community converter showed about 0.015 USDT per Star in Aug 2025 — [bes-dev Stars converter](https://bes-dev.github.io/telegram_stars_rates). The official ToS frames the payout as a fixed USD equivalent ($0.013).
- [OFFICIAL] Buyers keep access to unlocked posts even after deletion, and Telegram can't fully prevent redistribution — [Telegram ToS for Content Creators](https://telegram.org/tos/content-creator-rewards)

### Inferences
- **Effective take, illustrative, assuming about $0.02 retail per Star:**
  - Telegram creator: about $0.013 / $0.02 ≈ **65%** of buyer spend, then minus about 5% Fragment, ≈ **62%**, then minus exchange or bank fees.
  - Fanvue: **80%**, minus payout and FX costs. These are method-dependent and can be material for international wires.

  On a $10 fan purchase, that's roughly $6.2 via Telegram vs. about $8.0 via Fanvue before payout costs. Retail Star prices vary by country and purchase channel, so treat this as an approximation.
- **Payout friction:**
  - Telegram needs a crypto wallet and an exchange off-ramp with KYC, carries possible TON price exposure, and holds funds for 21 days.
  - Fanvue pays fiat to bank or wallets after a 7-day pending period.
  - For an operator outside the US/EU, exchange or bank access may be the deciding factor (not researched).
- **Buyer trust and conversion:**
  - Telegram purchases are one-tap through Apple or Google: familiar, discreet, and no new account or card disclosure. That favors impulse buys of low-ticket teasers (e.g., 50–250 Stars).
  - Fanvue asks for signup and a card, which loses some buyers. In exchange it offers subscriptions, DMs, a bigger catalog, and a transparent AI label.
  - A sensible split: Telegram for cheap teaser unlocks and community; Fanvue for subscription, full lingerie/implied/nude sets, and personalized content. Make Fanvue-only offers (trial links, bundles) the main CTA in Telegram.
- **Compliance:** selling nude content via paid media in a **private** channel isn't explicitly banned by Telegram's ToS, which only addresses illegal porn in public spaces. It still carries report and App Store risk (Section 6), while Fanvue explicitly supports adult content plus AI with disclosure. Keeping explicit content on Fanvue is the lower-risk default.

### Gaps
- Fanvue's official minimum payout per method and its per-method fees weren't confirmed. Third-party guides mention about $20 minimums and weekly payouts, but the official page says only "minimum threshold applicable to your chosen withdrawal method".
- Fanvue's referral program, and any Fanvue rule on promoting or selling the same content on other paid platforms, weren't researched.
- Current retail Star prices by region and channel (iOS vs. Android vs. Fragment) weren't found in English-language sources; Russian-language sources cover this, for the other researcher.

---

## 10. Conversion benchmarks: X → Telegram → Fanvue

### Takeaway
There are **no reliable, independently measured public benchmarks** for an X → Telegram → Fanvue funnel, and none specific to AI personas or the mature/fitness niche. What exists:
- Agency and vendor claims cluster around **3–8%** of engaged X traffic or DM responders converting to paid subscribers on OnlyFans-style platforms. A "4.2% average" is cited without methodology.
- Practitioners say most AI-model operations stall at the click-to-paying-chat step.
- Top-of-funnel numbers from Buffer's dataset: median about 600 impressions per post for Premium vs. under 100 for non-Premium, and median engagement about 0.4–0.55% for Premium.

Benchmarks should be built from the client's own tracked links.

### Cited Findings
- [VENDOR] SirenCY (an agency):
  - Defines a "3–7% average conversion rate" for X traffic to paid subscribers, while its own FAQ says there is "no reliable public benchmark".
  - Claims 1,000–3,000 free and 200–400 paid subscribers a month by day 60–90.
  - Sets targets (not measurements) of 2–5% engagement rate and 1–3% link-click rate.

  Source: [SirenCY](https://www.sirency.com/blog/onlyfans-twitter-x-marketing-guide-2026)
- [VENDOR] A mass-DM vendor estimates 3–8% of X DM responders become paying subscribers, "heavily" dependent on funnel quality — [Desirely](https://www.desirely.co/en/blog/x-twitter-mass-dm-onlyfans-agencies). Mass cold DMs violate X's anti-spam rules (Section 4).
- [VENDOR] A "2026 data report" page lists X/Twitter at a 4.2% average conversion rate, with vague methodology — [OnlyFans-finder statistics](https://onlyfans-finder.netlify.app/statistics/onlyfans-social-media-promotion-trends). An OFM course page attributes a 4.2% platform-wide visitor-to-subscriber figure to "OnlyTraffic (2025)" — [OFM course blog](https://ofm-course.pages.dev/blog/traffic-marketing-conversion-optimization-onlyfans-non-ai-agencies/)
- [DATA] For top-of-funnel planning: median impressions per post are under 100 for regular accounts, about 600 for Premium, and over 1,550 for Premium+. Median engagement is 0% for regular accounts vs. about 0.49–0.55% across Premium tiers. Non-Premium link posts had a median 0% engagement after March 2025. — [Buffer](https://buffer.com/resources/x-premium-review/)
- [ANECDOTAL] The conversion layer, turning a click into a paying chat, is described as where "90% stall" in AI-girlfriend operations — [BlackHatWorld operator journal](https://www.blackhatworld.com/posts/21235455/)
- [DATA/VENDOR] AI creators reached about 15% of Fanvue GMV by mid-2025, which shows the funnel can work at scale, though Sacra publishes no funnel rates — [Sacra](https://sacra.com/research/ai-onlyfans-at-100m-year/)

### Inferences
- **Treat 3–8% as an optimistic vendor range** for *engaged, high-intent* traffic converting to a paid subscription. It isn't a rate for followers or impressions, and adding Telegram as an intermediate hop introduces another drop-off.
- **Measurement framework the client can implement without new tools:**
  1. X: impressions, profile visits, and bio/pinned link clicks (X analytics).
  2. Telegram: joins per *named invite link* (one link per source: X bio, X pinned, IG, Threads, each paid placement), plus post views per subscriber.
  3. Telegram → Fanvue: clicks via separate Fanvue tracking links per Telegram CTA, then free follows or trials, then paid subscriptions and PPV revenue per source.

  Compare cost per paying fan and 30-day revenue per paying fan across sources. Drop any source whose paying-fan yield stays near zero after about 2–4 weeks.
- **Expect X teaser accounts to convert better per click than SFW IG/Threads traffic**, since intent is higher, but to have a smaller reach ceiling (adult filter, UK/EU age gate). That's a hypothesis to validate with the tracked links above.

### Gaps
- No independent or academic data on X → Telegram or Telegram → Fanvue conversion rates.
- No AI-persona-specific or mature/fitness-niche-specific benchmarks.
- No data on retention or churn of fans acquired via Telegram vs. directly from X or IG.
