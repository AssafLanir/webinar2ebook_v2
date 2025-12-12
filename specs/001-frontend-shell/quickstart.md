# Quickstart: Webinar2Ebook Ground Zero - Frontend Shell

**Feature**: 001-frontend-shell
**Date**: 2025-12-09

## Prerequisites

- Node.js 18.x or 20.x (LTS recommended)
- npm 9.x+ or pnpm 8.x+
- Modern browser (Chrome, Firefox, Safari, or Edge)

## Initial Setup

### 1. Create Frontend Project

```bash
# From repository root
npm create vite@latest frontend -- --template react-ts
cd frontend
```

### 2. Install Dependencies

```bash
# Core dependencies
npm install @headlessui/react @dnd-kit/core @dnd-kit/sortable

# Dev dependencies
npm install -D tailwindcss postcss autoprefixer
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
npm install -D @playwright/test
```

### 3. Initialize Tailwind CSS

```bash
npx tailwindcss init -p
```

Update `tailwind.config.js`:

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

Update `src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### 4. Configure Vitest

Create `vitest.config.ts`:

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './tests/setup.ts',
  },
})
```

Create `tests/setup.ts`:

```typescript
import '@testing-library/jest-dom'
```

### 5. Configure Playwright

```bash
npx playwright install
```

Create `playwright.config.ts`:

```typescript
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  webServer: {
    command: 'npm run dev',
    port: 5173,
    reuseExistingServer: !process.env.CI,
  },
})
```

## Directory Structure Setup

```bash
# Create directory structure
mkdir -p src/components/{common,layout,tab1,tab2,tab3,tab4}
mkdir -p src/{context,pages,types,data,utils}
mkdir -p tests/{unit,component,e2e}
mkdir -p tests/component/{tab1,tab2,tab3,tab4}
mkdir -p tests/unit/context
```

## Running the Application

### Development Server

```bash
cd frontend
npm run dev
# Opens at http://localhost:5173
```

### Run Tests

```bash
# Unit + Component tests
npm run test

# E2E tests
npm run test:e2e
```

### Build for Production

```bash
npm run build
npm run preview
```

## Package.json Scripts

Add to `frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:e2e": "playwright test",
    "lint": "eslint src --ext ts,tsx"
  }
}
```

## Implementation Order

Follow this order for incremental development:

### Phase 1: Foundation
1. `src/types/project.ts` - TypeScript interfaces
2. `src/context/ProjectContext.tsx` - State management
3. `src/utils/idGenerator.ts` - UUID generation helper

### Phase 2: Common Components
4. `src/components/common/Button.tsx`
5. `src/components/common/Input.tsx`
6. `src/components/common/Textarea.tsx`
7. `src/components/common/Select.tsx`
8. `src/components/common/Modal.tsx`
9. `src/components/common/Card.tsx`

### Phase 3: Layout & Navigation
10. `src/components/layout/TabBar.tsx`
11. `src/components/layout/TabNavigation.tsx`
12. `src/components/layout/ProjectHeader.tsx`
13. `src/pages/LandingPage.tsx`
14. `src/pages/WorkspacePage.tsx`

### Phase 4: Tab 1 (Transcript, Outline & Resources)
15. `src/components/tab1/TranscriptEditor.tsx`
16. `src/components/tab1/OutlineItem.tsx`
17. `src/components/tab1/OutlineEditor.tsx`
18. `src/components/tab1/ResourceItem.tsx`
19. `src/components/tab1/ResourceList.tsx`

### Phase 5: Tab 2 (Visuals)
20. `src/components/tab2/VisualCard.tsx`
21. `src/components/tab2/VisualGallery.tsx`
22. `src/components/tab2/AddCustomVisual.tsx`

### Phase 6: Tab 3 (Draft)
23. `src/components/tab3/StyleControls.tsx`
24. `src/components/tab3/DraftEditor.tsx`

### Phase 7: Tab 4 (Final & Export)
25. `src/components/tab4/MetadataForm.tsx`
26. `src/components/tab4/StructurePreview.tsx`
27. `src/components/tab4/ExportButton.tsx`
28. `src/utils/exportHelpers.ts`

### Phase 8: Sample Data & Polish
29. `src/data/sampleData.ts`
30. Integration and E2E tests

## Verification Checklist

After setup, verify:

- [ ] `npm run dev` starts without errors
- [ ] Tailwind styles apply (test with a colored div)
- [ ] `npm run test` runs (can be empty initially)
- [ ] TypeScript compiles without errors
- [ ] Directory structure matches plan

## Troubleshooting

### Vite HMR not working
- Check that `@vitejs/plugin-react` is installed
- Verify `vite.config.ts` includes the react plugin

### Tailwind styles not applying
- Ensure `index.css` is imported in `main.tsx`
- Check `content` paths in `tailwind.config.js`

### Test environment issues
- Verify `jsdom` is in devDependencies
- Check `vitest.config.ts` has correct environment setting

### TypeScript path issues
- Add path aliases in `tsconfig.json` if needed:
  ```json
  {
    "compilerOptions": {
      "baseUrl": ".",
      "paths": {
        "@/*": ["src/*"]
      }
    }
  }
  ```
