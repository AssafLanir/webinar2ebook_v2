import type { OutlineItem, Resource, Visual } from '../types/project'

export const SAMPLE_TRANSCRIPT = `Welcome everyone to today's webinar on "Building Effective Digital Products."

I'm excited to share insights from years of experience working with product teams across various industries. Today, we'll cover the essential principles that separate successful digital products from those that fail to gain traction.

First, let's talk about user-centered design. The most successful products are built with a deep understanding of user needs, pain points, and behaviors. This means conducting user research early and often, not just at the beginning of a project.

Moving on to our second key point: iterative development. Gone are the days of waterfall development where you spend months building something only to find out users don't want it. Modern product development embraces quick iterations, testing assumptions early, and pivoting when necessary.

Third, let's discuss the importance of metrics and data-driven decisions. Every feature you build should be measurable. Define success metrics upfront, track them religiously, and use that data to inform your next steps.

Finally, we'll talk about cross-functional collaboration. Great products aren't built in silos. They require designers, developers, product managers, and stakeholders working together effectively.

Let me share a case study that illustrates these principles in action...

Thank you all for joining today. I hope these insights help you build better digital products.`

export const SAMPLE_OUTLINE: Omit<OutlineItem, 'id' | 'order'>[] = [
  {
    title: 'Introduction',
    level: 1,
    notes: 'Welcome and overview of the webinar topics',
  },
  {
    title: 'User-Centered Design',
    level: 1,
    notes: 'Understanding user needs and conducting research',
  },
  {
    title: 'Research Methods',
    level: 2,
    notes: 'Surveys, interviews, usability testing',
  },
  {
    title: 'Iterative Development',
    level: 1,
    notes: 'Quick iterations and testing assumptions',
  },
  {
    title: 'Metrics and Data',
    level: 1,
    notes: 'Defining success metrics and tracking them',
  },
  {
    title: 'Cross-Functional Collaboration',
    level: 1,
    notes: 'Working effectively across teams',
  },
  {
    title: 'Case Study',
    level: 1,
    notes: 'Real-world example illustrating the principles',
  },
  {
    title: 'Conclusion',
    level: 1,
    notes: 'Summary and key takeaways',
  },
]

export const SAMPLE_RESOURCES: Omit<Resource, 'id' | 'order'>[] = [
  {
    label: 'The Lean Startup by Eric Ries',
    urlOrNote: 'https://theleanstartup.com/',
    resourceType: 'url_or_note',
  },
  {
    label: "Don't Make Me Think by Steve Krug",
    urlOrNote: 'Classic UX design principles',
    resourceType: 'url_or_note',
  },
  {
    label: 'Product Management Resources',
    urlOrNote: 'https://www.productplan.com/learn/',
    resourceType: 'url_or_note',
  },
  {
    label: 'User Research Handbook',
    urlOrNote: 'Internal company documentation on conducting user research',
    resourceType: 'url_or_note',
  },
]

export const EXAMPLE_VISUALS: Omit<Visual, 'id' | 'order'>[] = [
  {
    title: 'Introduction Slide',
    description: 'Opening slide with webinar title and presenter info',
    selected: false,
    isCustom: false,
  },
  {
    title: 'Key Concepts Diagram',
    description: 'Visual overview of main topics covered',
    selected: false,
    isCustom: false,
  },
  {
    title: 'Process Flow Chart',
    description: 'Step-by-step workflow illustration',
    selected: false,
    isCustom: false,
  },
  {
    title: 'Data Comparison Table',
    description: 'Side-by-side comparison of options discussed',
    selected: false,
    isCustom: false,
  },
  {
    title: 'Architecture Overview',
    description: 'System or concept architecture diagram',
    selected: false,
    isCustom: false,
  },
  {
    title: 'Summary Infographic',
    description: 'Visual summary of key takeaways',
    selected: false,
    isCustom: false,
  },
]

export const SAMPLE_DRAFT_TEXT = `# Building Effective Digital Products

## Introduction

In today's rapidly evolving digital landscape, the ability to build products that truly resonate with users has become a critical competitive advantage. This ebook distills the key principles shared in our recent webinar into actionable insights you can apply immediately.

## Chapter 1: User-Centered Design

The foundation of any successful digital product is a deep understanding of your users. This means going beyond assumptions and demographics to truly understand the problems users face, the context in which they work, and the outcomes they desire.

### The Research Imperative

User research isn't a one-time activity but an ongoing discipline. Successful product teams conduct regular research through methods such as:

- **User interviews**: One-on-one conversations that uncover needs and pain points
- **Surveys**: Quantitative data collection to validate hypotheses at scale
- **Usability testing**: Observing real users interacting with your product
- **Analytics review**: Understanding actual user behavior patterns

## Chapter 2: Iterative Development

The days of lengthy waterfall development cycles are behind us. Modern product development embraces iteration, learning, and adaptation.

### The Build-Measure-Learn Loop

Each iteration should follow a simple cycle:
1. Build the smallest thing that lets you learn
2. Measure how users respond
3. Learn from the results and decide what to do next

## Chapter 3: Metrics and Data-Driven Decisions

"What gets measured gets managed." This principle is especially true in product development. Every feature, every change, every experiment should be tied to measurable outcomes.

### Defining Success Metrics

Before building anything, define:
- What success looks like for this feature
- How you will measure it
- What threshold indicates success or failure

## Chapter 4: Cross-Functional Collaboration

Great products emerge from great teams working together effectively. This requires breaking down silos and creating shared ownership of outcomes.

### Building Effective Teams

- Establish shared goals and metrics
- Create regular touchpoints for alignment
- Foster psychological safety for open discussion
- Celebrate wins together

## Conclusion

Building effective digital products is both an art and a science. By embracing user-centered design, iterative development, data-driven decisions, and cross-functional collaboration, you position your team for success.

Remember: the best products are never truly "finished"—they evolve continuously based on user feedback and changing market conditions.

---

*This ebook was generated from webinar content using Webinar2Ebook.*`
