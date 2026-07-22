# Adventure Boat Finder first-release audit

Generated from the two supplied Dan's Boat Life power-boat playlists.

## Source coverage

- Playlist entries discovered: 417 (213 walkthrough, 204 test drive)
- Entries appearing in both playlists: 15
- Unique video IDs discovered: 402
- Accessible records captured: 401
- Private videos: 1 (`rl97aUMrvqc`)
- Saved top comments: 11,769
- Full timestamped transcripts: 399
- Timestamped transcript segments stored: 53,306
- Transcript-derived evidence claims stored: 4,748
- Accessible records without a transcript: 2, both non-boat playlist outliers

## Identity and pairing gate

- Real boat videos with make, model and length: 398 of 398
- Non-boat playlist outliers: 3
- Low-confidence identities accepted for publication: 0
- Canonical make/model groups with walkthrough and test-drive evidence: 171
- Walkthrough-only canonical groups: 25
- Test-drive-only canonical groups: 13

No video is automatically publishable unless it has a complete identity and an identity confidence of at least 0.84. The launch catalogue applies a second gate requiring an explicit make/model mention and a transcript for every linked source video.

## Corpus taxonomy and decision fields

- Canonical boats: 209
- Real boat videos linked to those boats: 398
- Boat-only transcript segments examined: 53,177
- Category anchors and transcript-type candidates: 20
- Structured decision fields: 51
- Consolidated boat attribute values: 2,275
- Timestamped attribute evidence rows: 4,548
- Candidate category assignments: 272
- Timestamped category evidence rows: 608
- Uncanonicalised boat rows after consolidation: 0

Dan's supplied Adventure Boats, Fast Explorers, Sport Yachts, Luxury RIBs and Luxury Med Day Boats remain editorial anchors. Additional transcript-type candidates are held for the category workshop. Categories may overlap, and no absent transcript tag is interpreted as a negative feature.

## Launch catalogue

- Adventure Boats in the first public catalogue: 15
- Source videos: 30
- Boats passing all publication checks: 15
- Timestamped transcript excerpts: 30
- Boats enriched with read-only sold-market context: 15
- Regional/global market metric rows stored: 75
- Mission profiles stored: 75

The sold-boats SQLite database is opened with `mode=ro&immutable=1` and `PRAGMA query_only=ON`. It is never modified and BoatWizard is not scraped.

## Verified buyer journey

- PostgreSQL schema applied successfully
- Every answer saved as a revisioned decision
- Earlier-answer editing verified
- Five-result shortlist persistence verified
- Resume secret held in the URL fragment, not the query string
- Bad resume token rejection verified
- Completion and email outbox creation verified
- Desktop and 390 x 844 mobile layouts verified
- Transcript tags contribute explainable mission-fit reasons without becoming unsupported hard exclusions

SMTP delivery is environment-driven. Without SMTP credentials, completed emails remain safely queued in `email_outbox` for a worker or configured deployment to send.
