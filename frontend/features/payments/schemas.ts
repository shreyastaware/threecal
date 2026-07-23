import { z } from "zod";

import { OAUTH_PAYMENT_PROVIDERS } from "./api";

export const oauthPaymentProviderSchema = z.enum(OAUTH_PAYMENT_PROVIDERS);

export const oauthAuthorizationSchema = z.object({
  authorization_url: z.url(),
});

export type OAuthPaymentProviderValue = z.infer<
  typeof oauthPaymentProviderSchema
>;
