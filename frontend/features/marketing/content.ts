// Static marketing copy kept in one place so sections stay presentational.
import type { LucideIcon } from "lucide-react";
import {
  BellRing,
  CalendarSync,
  LayoutTemplate,
  ShieldCheck,
  Wallet,
} from "lucide-react";

export const TRUSTED_ROLES = [
  "Consultants",
  "Experts",
  "Coaches",
  "Lawyers",
  "Doctors",
  "Therapists",
] as const;

export interface SocialLink {
  name: string;
  href: string;
  icon: "instagram" | "x" | "reddit";
}

export const SOCIAL_LINKS: SocialLink[] = [
  { name: "Instagram", href: "https://www.instagram.com/threecaldotcom/", icon: "instagram" },
  { name: "X (Twitter)", href: "https://x.com/threecaldotcom", icon: "x" },
  { name: "Reddit", href: "https://www.reddit.com/r/threecal/", icon: "reddit" },
];

export interface HowItWorksStep {
  index: string;
  title: string;
  description: string;
}

export const HOW_IT_WORKS: HowItWorksStep[] = [
  {
    index: "01",
    title: "Create",
    description:
      "Set up your booking page, event types, prices and availability in a few minutes.",
  },
  {
    index: "02",
    title: "Share",
    description:
      "Send one link. Clients pick a slot that suits them, no need of back-and-forth emails.",
  },
  {
    index: "03",
    title: "Get booked",
    description:
      "They pay upfront and the appointment lands on your calendar, confirmed.",
  },
];

export interface Benefit {
  icon: LucideIcon;
  title: string;
  description: string;
}

export const BENEFITS: Benefit[] = [
  {
    icon: Wallet,
    title: "Get paid upfront",
    description:
      "Collect payment the moment a slot is booked, so your time is always covered.",
  },
  {
    icon: ShieldCheck,
    title: "Reduce no-shows",
    description:
      "Prepaid appointments mean clients show up. Fewer gaps, less chasing.",
  },
  {
    icon: CalendarSync,
    title: "Calendar sync",
    description:
      "Two-way sync keeps your availability accurate across every calendar you use.",
  },
  {
    icon: BellRing,
    title: "Automatic reminders",
    description:
      "Timely email reminders go out to you and your clients before every session.",
  },
  {
    icon: LayoutTemplate,
    title: "Custom booking page",
    description:
      "A booking page that carries your name, your rates and your brand.",
  },
];

export interface BookingStat {
  value: string;
  label: string;
}

export const BOOKING_STATS: BookingStat[] = [
  { value: "42%", label: "Fewer no-shows on average" },
  { value: "3 min", label: "To publish a booking page" },
  { value: "100%", label: "Of sessions paid before they start" },
];

export interface Testimonial {
  quote: string;
  name: string;
  role: string;
}

export const TESTIMONIALS: Testimonial[] = [
  {
    quote:
      "I stopped losing hours to no-shows. Every booking is paid before it hits my calendar.",
    name: "Maya R.",
    role: "Independent consultant",
  },
  {
    quote:
      "Sharing one link changed everything. Clients book, pay and show up — I just do the work.",
    name: "Daniel K.",
    role: "Executive coach",
  },
];

export interface FaqItem {
  question: string;
  answer: string;
}

export const FAQ: FaqItem[] = [
  {
    question: "Do clients need an account?",
    answer:
      "No. Clients simply open your link, choose a time, pay and confirm. No sign-up required.",
  },
  {
    question: "Can I charge before bookings?",
    answer:
      "Yes — that is the point of threecal. Payment is collected upfront when a slot is booked, so your time is protected.",
  },
  {
    question: "Which calendars are supported?",
    answer:
      "Google Calendar and other major providers via two-way sync, with more integrations rolling out.",
  },
  {
    question: "What payment providers are supported?",
    answer:
      "Payments run through pluggable providers such as Stripe, with additional gateways being added over time.",
  },
];
