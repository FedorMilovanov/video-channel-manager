# Video Channel Manager — Privacy Policy

**Effective:** 13 November 2026  
**Developer and data controller:** [Fedor Milovanov](https://github.com/FedorMilovanov)  
**Application:** Video Channel Manager (local, owner-operated software)

This is the privacy policy of **Video Channel Manager**, not a privacy policy for a connected YouTube channel or a separate public website. Video Channel Manager uses **YouTube API Services**, including the YouTube Data API.

## Users and scope

Video Channel Manager is mainly a private application run by the owner for explicitly authorized video-channel management and editorial workflows. It does not provide open registration or paid accounts for the public. Channel projects have separate identities and Google OAuth authorizations; a credential for one channel does not authorize changes to another.

The tool can work with The Legendary Poet, Фёдор Милованов / Господь Бог — Сила Моя, and other separately authorized media projects. This policy covers YouTube-connected features of the application, regardless of which authorized channel is selected.

## What information is accessed

Depending on an explicitly enabled operation, the application can access and process:
- the connected YouTube channel identifier, channel name and account alias;
- video identifiers and metadata, including titles, descriptions, languages, localizations, publication and privacy status;
- captions/subtitle tracks, playback or publishing metadata, playlists and comments where applicable to the authorized workflow;
- OAuth access tokens, refresh tokens, granted scopes and token-expiration metadata needed for Google authorization;
- locally created editorial plans, audit snapshots, logs, checksums, API readback results and operation journals.

The precise data accessed depend on the features invoked and the permissions granted by the authorizing Google account. Video Channel Manager does not request or store the user's Google password.

## Why and how data are used

Data are processed only for owner-authorized tasks, including inventory and auditing, media management, translation/localization, subtitle management, editorial verification, scheduling or owner-approved updates. The application verifies the selected project and exact YouTube target before making changes. Recorded operational evidence is used to diagnose failures and avoid accidental duplicate writes.

Google/YouTube receive data and requests transmitted through their official API infrastructure. Local working files, account tokens and operational logs are kept in files on the operator's machine; some authorized workflows may involve approved computing services needed to prepare or validate media. Authorized YouTube data are not sold or supplied to data brokers, unrelated advertisers or third parties for targeted advertising. The application does not operate a public ad-supported website, use third-party advertising trackers, or set browser marketing cookies. When the owner uses Google's authorization pages, Google processes that activity under its own privacy policy.

## Storage and protection

OAuth token files are kept separately from the public source repository in local secret directories. Normal application requests to YouTube API Services use encrypted HTTPS connections. Access to the local data is limited to the authorized operator and the operator's expressly approved assistants or processors. The application does not intentionally publish tokens or private YouTube account records to the public source repository.

## Retention, refresh and deletion

Authorized data are kept only while needed for the purposes for which the owner granted access. Data categories subject to the YouTube API Developer Policies' refresh/deletion limits are refreshed or deleted within the applicable period (generally no more than 30 days unless an exception applies). Authorization validity must be reconfirmed as required by YouTube. A user may request deletion of locally stored personal/API data at any time. Such requests are to be fulfilled promptly and within the period required by YouTube, including seven calendar days where applicable. Removing local files does **not** remove media or data stored by YouTube; use the YouTube website or an authorized API client to remove content there.

To request deletion or ask a privacy question, contact the maintainer via [this repository's issue/contact page](https://github.com/FedorMilovanov/video-channel-manager/issues/new), requesting a **private contact method**. Do not put personal information, account credentials or sensitive details in a public issue. The maintainer will arrange private handling of the request.

## How to revoke access

The authorizing user can revoke the application's Google account permissions at any time at [Google Account third-party access settings](https://security.google.com/settings/security/permissions). Revocation stops further authorized use of that credential and requires cleanup of the associated locally retained API data according to YouTube's applicable requirements. A user may additionally request local deletion through the contact method above.

## Terms, third-party policies and updates

By using YouTube-connected features, users agree to the [YouTube Terms of Service](https://www.youtube.com/t/terms). The product is subject to the [YouTube API Services Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service) and [YouTube API Developer Policies](https://developers.google.com/youtube/terms/developer-policies). Google processes its own services under the [Google Privacy Policy](https://policies.google.com/privacy).

This policy is available to the owner before continuing use of Google-connected features and should be reviewed when the scope of processing changes. New uses that materially change how authorized data are processed require updated notice and, where applicable, new consent.

**Policy owner:** Fedor Milovanov  
**Last updated:** 13 November 2026
