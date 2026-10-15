import { runDetector } from '@/lib/detector';

// jobs.ashbyhq.com, hosted or embedded in a company career page.
export default defineContentScript({
  matches: ['*://jobs.ashbyhq.com/*'],
  allFrames: true,
  runAt: 'document_idle',
  main() {
    runDetector({
      ats: 'ashby',
      strongSuccessText: /your application was successfully submitted/i,
      successTextAfterSubmit: /thank you for (applying|your application)|application (was )?(successfully )?submitted|we.ll be in touch/i,
    });
  },
});
