# Accessibility Roadmap

**Last updated**: 2026-03-08  
**Status**: Planning

---

## Overview

**Goal**: Make the app usable by people with disabilities. Target WCAG 2.1 AA (or equivalent) where applicable. Address screen readers, keyboard/navigation, contrast, and touch targets.

**Current state**: Some accessibility may exist (e.g. basic labels); comprehensive audit and systematic improvements are needed.

---

## Target standards

| Standard | Scope |
|----------|-------|
| **WCAG 2.1 Level AA** | Web (Expo web build). Use as guidance for native where applicable. |
| **iOS Accessibility** | VoiceOver, Dynamic Type, Reduce Motion. |
| **Android Accessibility** | TalkBack, font scaling, touch target size. |

---

## Backend requirements

Accessibility is primarily a frontend and design concern. Backend contributes in these areas:

| Area | Requirement |
|------|-------------|
| **Error messages** | Return clear, actionable `detail` messages. Avoid raw stack traces or technical jargon. Messages should be understandable when read by a screen reader. |
| **Response structure** | Use consistent field names and shapes so client can reliably map to accessible labels (e.g. `label` vs `name` for display text). |
| **Semantic data** | Where the API returns content for display (e.g. plate names, restaurant info), ensure it is suitable for alt text or announcements. No special backend changes required if data is already descriptive. |
| **Rate limit / error responses** | Include human-readable messages in 429, 500 responses so the client can announce them accessibly. |

### Questions for backend

- [ ] Confirm error `detail` strings are user-facing (no stack traces in production).
- [ ] Any API fields that could support accessibility metadata (e.g. `alt_text` for images)? Likely out of scope for now; images are client-rendered.

---

## Frontend requirements

### Screen readers (VoiceOver, TalkBack)

| Component | Requirement |
|-----------|-------------|
| **Images** | `accessibilityLabel` (or `alt`) for meaningful images. Decorative images: `accessible={false}` or empty alt. |
| **Buttons / links** | Descriptive `accessibilityLabel`. Avoid "Click here" — use "Add address", "Change password", etc. |
| **Form fields** | `accessibilityLabel` linked to input; `accessibilityHint` where helpful. |
| **Lists** | Use semantic list roles; `accessibilityRole="list"` / `listitem` where supported. |
| **Custom components** | Ensure focusable elements receive focus in logical order; announce state changes (e.g. "Filter applied"). |
| **Dynamic content** | Live regions (`accessibilityLiveRegion`) for toast messages, loading completions, errors. |

### Keyboard and navigation

| Area | Requirement |
|------|-------------|
| **Web** | Full keyboard navigation; visible focus indicators; logical tab order. |
| **Native** | Support external keyboard where applicable (e.g. iPad); focus management in modals. |
| **Skip links** | On web, provide "Skip to main content" for keyboard users. |

### Visual

| Area | Requirement |
|------|-------------|
| **Color contrast** | Text meets WCAG AA (4.5:1 for normal, 3:1 for large). Don't rely on color alone for meaning. |
| **Touch targets** | Minimum 44x44 pt (iOS) / 48x48 dp (Android) for tap targets. |
| **Focus indicators** | Visible focus ring on interactive elements. |
| **Reduce motion** | Respect `prefers-reduced-motion`; avoid or shorten animations when set. |

### Platform-specific (React Native / Expo)

| Platform | Props / API |
|----------|-------------|
| **iOS** | `accessibilityLabel`, `accessibilityHint`, `accessibilityRole`, `accessibilityState`; `accessible`; Dynamic Type via `allowFontScaling` or text scaling. |
| **Android** | Same plus `importantForAccessibility`; `accessibilityLiveRegion`. |
| **Web** | `aria-*` attributes, `role`, `tabIndex`; use React Native Web's mapping or supplement with DOM attributes. |

---

## Testing

| Method | Purpose |
|--------|---------|
| **Automated** | `eslint-plugin-jsx-a11y`; `@axe-core/react` (web); `react-native-accessibility-engine` or similar. |
| **Manual** | Turn on VoiceOver (iOS) and TalkBack (Android); navigate key flows. |
| **Audit** | Periodic WCAG audit (e.g. Lighthouse, aXe) on web build. |
| **User testing** | Recruit users who rely on assistive tech for critical paths. |

---

## Implementation phases

1. **Audit**: Run automated tools; document current gaps. Prioritize by user impact (login, Explore, Profile, checkout).
2. **Foundations**: Add `accessibilityLabel` to all interactive elements; ensure form fields have labels; fix contrast issues in theme.
3. **Navigation**: Verify focus order; add skip links (web); test with screen reader on critical flows.
4. **Polish**: Live regions for dynamic content; reduce-motion support; touch target sizing.
5. **Ongoing**: Include a11y in code review; add a11y tests for critical components.

---

## References

- [WCAG 2.1](https://www.w3.org/WAI/WCAG21/quickref/)
- [React Native Accessibility](https://reactnative.dev/docs/accessibility)
- [Expo Accessibility](https://docs.expo.dev/guides/accessibility/)
