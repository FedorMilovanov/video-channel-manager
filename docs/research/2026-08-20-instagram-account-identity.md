# Instagram Professional account identity — provider evidence boundary

Status: research ledger  
Owner issue: #492  
Researched: 2026-08-20  
Scope: official Meta/Instagram API behavior relevant to exact project/account binding

## Why this exists

A public Instagram username is mutable presentation metadata. It is not a safe execution target for a multi-project publisher.

The future Instagram executor must operate only after a provider-authenticated **Instagram Professional account ID** has been observed and then explicitly bound to one repository `project_key`. The provider observation and the project binding are separate evidence objects.

No access token, client secret or refresh token belongs in either evidence object.

## Official API models currently available

Meta currently documents two distinct Instagram Professional API login models.

### Instagram API with Instagram Login

Official Meta documentation describes this route as direct access for Instagram professional accounts — businesses and creators.

Key properties relevant to identity proof:

- host: `graph.instagram.com`;
- access token type: Instagram User access token;
- login type: Business Login for Instagram;
- basic identity permission: `instagram_business_basic`;
- content publishing permission is separate: `instagram_business_content_publish`;
- a linked Facebook Page is **not required** for this API setup;
- this setup does not provide ads or tagging access.

For an identity-only observation, `instagram_business_content_publish` is deliberately not required by the repository contract. Publishing authority must remain a later, separate capability check.

Official Meta sources:

- Instagram API collection:
  https://www.postman.com/meta/instagram/collection/6yqw8pt/instagram-api
- Instagram API documentation / Instagram Login sections:
  https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api
- Meta Instagram workspace documentation noting the Instagram Login scope names and that a Facebook Page is not required:
  https://www.postman.com/meta/workspace/instagram/documentation/23987686-9386f468-7714-490f-9bfc-9442db5c8f00

### Instagram API with Facebook Login

Official Meta documentation describes this route for Instagram Professional accounts connected through Facebook Login for Business.

Key identity properties:

- host: `graph.facebook.com`;
- the Professional Instagram account must be linked to a Facebook Page for this setup;
- `GET /me/accounts?fields=name,access_token,tasks,instagram_business_account` is the documented Page discovery path;
- the returned `instagram_business_account` object supplies the Instagram professional account identity associated with the Page;
- relevant discovery/basic permissions include `pages_show_list` and `instagram_basic`;
- publishing permission is separately `instagram_content_publish`.

Official Meta source:

- Instagram API documentation / Facebook Login token and Page discovery flow:
  https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api

## Access level

Meta's current Instagram documentation distinguishes:

- Standard Access for professional accounts the app owner owns or manages and has added to the app;
- Advanced Access when the app serves professional accounts it does not own or manage.

This project currently needs only its own managed brand accounts. That does not remove the need for exact account-ID proof; it only affects the Meta app review/access-level path.

## Repository evidence model

### 1. `InstagramAccountObservation`

A provider-read evidence record only. It freezes:

- login model;
- API host/version;
- numeric Instagram Professional account ID;
- username observed at that moment, as non-authoritative display metadata;
- observed account type when returned;
- linked Facebook Page ID only for the Facebook Login model;
- exact granted scope names, but **never the token itself**;
- observation timestamp;
- SHA-256 of the raw provider response bytes.

The model rejects a cross-wired host/login combination and enforces the basic permission appropriate to that login model.

### 2. `InstagramProjectBinding`

Offline human-reviewed mapping from one exact provider observation to one canonical repository `project_key`.

The binding freezes:

- `project_key`;
- numeric Instagram Professional account ID;
- SHA-256 of the exact observation artifact;
- username snapshot for operator readability only;
- human reviewer and approval timestamp.

It performs no provider write and grants no publishing capability.

### 3. `InstagramProjectBindingRegistry`

The registry rejects:

- duplicate project keys;
- one numeric Instagram Professional account ID assigned to more than one project.

This is the cross-brand safety boundary required before any future write executor can choose a Meta target.

## Explicit non-goals

This research/contract layer does not:

- run OAuth;
- store access tokens;
- create a Meta app;
- create or link Facebook Pages;
- infer an account ID from a username;
- publish, edit, delete, like, comment, follow, message or advertise;
- treat a successful identity read as `instagram_content_publish` authorization;
- select between Instagram Login and Facebook Login merely because a Facebook Page happens to exist.

The eventual read-only Meta client should produce the raw provider response and typed observation. Only after that observation exists should an operator create the explicit project binding.
