import { runDetector } from '@/lib/detector';

// Hosted boards (job-boards / boards.greenhouse.io) and the embed iframes that
// company career pages load, so allFrames is on.
export default defineContentScript({
  matches: ['*://*.greenhouse.io/*'],
  allFrames: true,
  runAt: 'document_idle',
  main() {
    runDetector({
      ats: 'greenhouse',
      isConfirmationUrl: (url) => /\/confirmation\/?$/.test(url.pathname),
      successTextAfterSubmit: /thank you for applying|application has been (received|submitted)/i,
    });
  },
});
