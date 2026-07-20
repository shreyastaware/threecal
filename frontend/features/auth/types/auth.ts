export type User = {
  id: string;
  email: string;
  full_name: string;
  username: string | null;
  bio: string | null;
  timezone: string;
  avatar_url: string | null;
  is_active: boolean;
  is_email_verified: boolean;
  created_at: string;
};

export type LoginInput = {
  email: string;
  password: string;
};

export type RegisterInput = LoginInput & {
  full_name: string;
};

export type AuthResponse = {
  user: User;
};
