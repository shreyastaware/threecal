import type { OAuthPaymentProvider } from "@/features/payments/api";

type PaymentProviderLogo = {
  height: number;
  src: `https://${string}`;
  width: number;
};

export const PAYMENT_PROVIDER_LOGOS = {
  stripe: {
    height: 512,
    src: "https://assets.threecal.com/payment-providers/stripe.svg",
    width: 512,
  },
  paypal: {
    height: 48,
    src: "https://assets.threecal.com/payment-providers/paypal.svg",
    width: 48,
  },
  razorpay: {
    height: 67,
    src: "https://assets.threecal.com/payment-providers/razorpay.svg",
    width: 316,
  },
  cashfree: {
    height: 876,
    src: "https://assets.threecal.com/payment-providers/cashfree.jpg",
    width: 3000,
  },
} satisfies Record<OAuthPaymentProvider, PaymentProviderLogo>;
