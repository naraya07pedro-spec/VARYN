# VARYN Premium Workspace | Alpha 5

Reference: the **second, Premium Workspace** concept approved by the project owner on 2026-11-06. This change implements the actual local Windows interface, not a static concept image.

## Reference fidelity

- Deep slate/navy, restrained violet accents and Segoe UI typography.
- Compact VARYN left sidebar with Chat, Tugas, Aplikasi, Riwayat and Pengaturan, and a personal identity footer.
- Full-width responsive **purple-pink dusk mountain hero** rendered inside the app with `TwilightBanner`. No downloaded images or fake OS screenshots.
- VARYN headline and natural Indonesian welcome copy over the landscape.
- Centered dark chat composer, subtle purple border, mode chooser and one send button.
- Three rounded shortcut cards: **Tugas**, **Aplikasi**, **Template**. Each card works: navigate to the local task store, show the explicitly disconnected catalog, or prefill an editable work-plan prompt.
- On first accepted send the UI switches to a readable conversation transcript; provider routing, explicit approvals, offline-simulation labeling and session budget are inherited from the existing `ChatSurface` implementation.
- Riwayat displays *this process's volatile chat transcript only*; never claims permanent conversation storage.
- Responsive canvas resizing. The reference is a design target, not a claim of pixel-identical images or font rasterization across Windows versions.

## Safety and operational scope

Model API credentials are NOT inherited from ChatGPT; OpenRouter/DeepSeek calls require independent credentials and exact outgoing prompt approval. The offline response is a clearly labeled simulation. App connectors are not yet authenticated. Due tasks only update state while the desktop is open; no automatic task execution. SQLite task metadata is unencrypted. The package remains experimental and unsigned.

## Shipping

The intentional `release:` CI commit targets `v0.1.0-alpha.5`. Only report a downloadable Alpha 5 after the exact Windows/Ubuntu CI, actual PyInstaller bundle and GitHub prerelease publication jobs complete successfully. PR #1 remains OPEN/DRAFT; no merge into `main`.
