# Genuine demo capture guide (do not fabricate screenshots)

**Current state:** No genuine Windows app screenshot or GIF has been added to VARYN's repository. The GitHub-hosted GUI build and test logs are not video recordings.

## 60-second honest demo storyboard

1. Show Windows desktop with VARYN Portable opened **as a normal user**. Hide account identifiers, notifications, paths, and network tokens.
2. Show **Model Control Center** default network OFF and fake model selected.
3. Add the fictional reviewed fake offer, preview the one-request cost estimate, and show the exact-send consent prompt.
4. Approve the fake run. Display the unmistakably marked `FAKE:` response and point out that this step involved **zero external provider requests**.
5. If and only if a real provider has been authorized and tested on the owner's device, record a second short sequence showing a harmless self-authored question, the fresh real-task/network toggles, the exact consent prompt, and a real answer. Blur account identifiers; never show or record API credentials.
6. Finish with a clear caption: **experimental prototype, not official consumer-app history sync, no provider billing guarantee**.

## Suggested assets

- `docs/media/windows-model-center.png`: authentic app screenshot showing synthetic, offline default.
- `docs/media/model-center-demo.gif`: authentic 10–30 second recording of a fake-model request.
- `docs/media/real-provider-demo.gif`: OPTIONAL, only after actual owner-device provider success. Explicitly label the real provider and avoid unverified upstream claims.

Use a trusted Windows desktop recording utility already installed; review every frame for personal data and tokens. Compress to keep repository load reasonable. Do not use AI image generation to impersonate a live screenshot or actual user-device integration.

## Release gate

The README must not link to these paths until the corresponding real files have actually been recorded and committed. New users should not infer that a CI smoke-test video demonstrates owner-PC deployment.
