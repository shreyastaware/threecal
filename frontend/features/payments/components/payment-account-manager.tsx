"use client";

import { Dialog } from "@base-ui/react/dialog";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AtSign,
  Building2,
  Check,
  CheckCircle2,
  CircleAlert,
  Clock3,
  CreditCard,
  IdCard,
  Landmark,
  LoaderCircle,
  LockKeyhole,
  MapPin,
  Pencil,
  Phone,
  RefreshCw,
  ShieldCheck,
  Tags,
  UserRound,
  X,
} from "lucide-react";
import posthog from "posthog-js";
import { useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/features/auth/hooks/use-auth";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import {
  paymentsApi,
  type PaymentAccount,
  type PaymentAccountCreate,
  type PaymentAccountUpdate,
} from "@/features/payments/api";
import {
  PAYMENT_ACCOUNT_KEY,
  usePaymentAccount,
} from "@/features/payments/hooks/use-payment-account";
import {
  activationStatusLabels,
  businessCategoryOptions,
  businessTypeOptions,
  normalizePhone,
  paymentAccountFormSchema,
  personalPanBusinessTypes,
  subcategoriesFor,
  type PaymentAccountFormValues,
} from "@/features/payments/schemas";
import { getErrorMessage } from "@/lib/api/client";

function formValues(
  account: PaymentAccount | null | undefined,
  user: { full_name: string; email: string } | null,
): PaymentAccountFormValues {
  return {
    account_name: account?.account_name ?? user?.full_name ?? "",
    account_email: account?.account_email ?? user?.email ?? "",
    phone: account?.phone ?? "",
    business_type: account?.business_type ?? "individual",
    business_name: account?.business_name ?? "",
    business_category: account?.business_category ?? "",
    business_subcategory: account?.business_subcategory ?? "",
    pan: "",
    street1: account?.street1 ?? "",
    street2: account?.street2 ?? "",
    city: account?.city ?? "",
    state: account?.state ?? "",
    postal_code: account?.postal_code ?? "",
    branch_ifsc_code: account?.branch_ifsc_code ?? "",
    account_number: "",
    beneficiary_name: account?.beneficiary_name ?? user?.full_name ?? "",
  };
}

function businessTypeLabel(value: PaymentAccount["business_type"]): string {
  return (
    businessTypeOptions.find((option) => option.value === value)?.label ?? value
  );
}

function categoryLabel(category: string | null, subcategory: string | null): string {
  if (!category) return "Not provided";
  const option = businessCategoryOptions.find((item) => item.value === category);
  const sub = subcategoriesFor(category).find((item) => item.value === subcategory);
  return [option?.label ?? category, sub?.label ?? subcategory].filter(Boolean).join(" · ");
}

function addressLabel(account: PaymentAccount): string {
  const parts = [account.street1, account.street2, account.city, account.state, account.postal_code].filter(Boolean);
  return parts.length ? parts.join(", ") : "Not provided";
}

function requirementLabel(fieldReference: string): string {
  return fieldReference.replace(/[._]/g, " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

function ReadOnlyDetail({
  icon: Icon,
  label,
  value,
  monospaced = false,
}: {
  icon: typeof UserRound;
  label: string;
  value: string;
  monospaced?: boolean;
}) {
  return (
    <div className="payment-detail-row">
      <Icon aria-hidden="true" size={16} />
      <div>
        <dt>{label}</dt>
        <dd className={monospaced ? "payment-masked-value" : ""}>{value}</dd>
      </div>
    </div>
  );
}

function PayoutStatus({
  account,
  syncing,
  onSync,
}: {
  account: PaymentAccount;
  syncing: boolean;
  onSync: () => void;
}) {
  const StatusIcon = account.payouts_enabled
    ? CheckCircle2
    : account.activation_status === "needs_clarification" || account.activation_status === "suspended"
      ? CircleAlert
      : Clock3;
  const summary = !account.payouts_configured
    ? "Online payments are not enabled on Threecal yet. Your details are saved and will be submitted once they are."
    : account.payouts_enabled
      ? "Paid bookings are enabled. Each payment is split automatically and your share settles to this bank account."
      : account.activation_status === "not_started"
        ? "Your details have not been submitted to Razorpay yet. Save them again or refresh to retry."
        : account.activation_status === "needs_clarification"
          ? "Razorpay needs a few corrections before payouts can start. Update the details listed below."
          : account.activation_status === "suspended"
            ? "Payouts are suspended. Contact support to restore paid bookings."
            : "Razorpay is verifying your bank account. Paid bookings open as soon as payouts are active.";

  return (
    <section className={`payout-status-panel payout-status-${account.activation_status}`}>
      <div className="payout-status-heading">
        <StatusIcon aria-hidden="true" size={18} />
        <div>
          <p>Payouts</p>
          <strong>{activationStatusLabels[account.activation_status]}</strong>
        </div>
        {account.payouts_configured && !account.payouts_enabled && (
          <button className="payment-edit-button" disabled={syncing} onClick={onSync} type="button">
            {syncing ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />} Refresh status
          </button>
        )}
      </div>
      <p className="payout-status-summary">{summary}</p>
      {account.requirements.length > 0 && (
        <ul className="payout-requirements">
          {account.requirements.map((requirement) => (
            <li key={`${requirement.field_reference}-${requirement.reason_code}`}>
              <strong>{requirementLabel(requirement.field_reference)}</strong>
              <span>{requirement.description ?? requirement.reason_code.replace(/_/g, " ")}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function PaymentAccountManager() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [editorOpen, setEditorOpen] = useState(false);
  const account = usePaymentAccount();
  const save = useMutation({
    mutationFn: ({
      existing,
      input,
    }:
      | { existing: false; input: PaymentAccountCreate }
      | { existing: true; input: PaymentAccountUpdate }) =>
      existing
        ? paymentsApi.updateAccount(input)
        : paymentsApi.createAccount(input),
    onSuccess: (updated, variables) => {
      queryClient.setQueryData(PAYMENT_ACCOUNT_KEY, updated);
      posthog.capture(
        variables.existing
          ? "payment_account_updated"
          : "payment_account_connected",
        {
          business_type: updated.business_type,
          activation_status: updated.activation_status,
        },
      );
      setEditorOpen(false);
      reset(formValues(updated, user));
    },
    // Details are saved before Razorpay is called, so refresh to switch to edit mode on retry.
    onError: () => void queryClient.invalidateQueries({ queryKey: PAYMENT_ACCOUNT_KEY }),
  });
  const sync = useMutation({
    mutationFn: paymentsApi.syncAccount,
    onSuccess: (updated) => queryClient.setQueryData(PAYMENT_ACCOUNT_KEY, updated),
  });
  const {
    register,
    reset,
    handleSubmit,
    setError,
    setValue,
    control,
    formState: { errors },
  } = useForm<PaymentAccountFormValues>({
    resolver: zodResolver(paymentAccountFormSchema),
    defaultValues: formValues(null, user),
  });
  const businessType = useWatch({ control, name: "business_type" });
  const businessCategory = useWatch({ control, name: "business_category" });
  const subcategoryOptions = subcategoriesFor(businessCategory);
  const personalPan = personalPanBusinessTypes.has(businessType);
  // Razorpay does not allow these to change once the linked account exists.
  const lockedIdentity = Boolean(
    account.data && account.data.activation_status !== "not_started",
  );

  function openEditor() {
    save.reset();
    reset(formValues(account.data, user));
    setEditorOpen(true);
  }

  function handleOpenChange(open: boolean) {
    if (save.isPending) return;
    setEditorOpen(open);
    if (!open) {
      save.reset();
      reset(formValues(account.data, user));
    }
  }

  const onSubmit = handleSubmit((values) => {
    const existing = Boolean(account.data);
    if (!existing && !values.account_number) {
      setError("account_number", {
        message: "Enter the bank account number",
      });
      return;
    }
    if (!existing && !values.pan) {
      setError("pan", { message: "Enter the PAN" });
      return;
    }

    const commonInput = {
      account_name: values.account_name.trim(),
      account_email: values.account_email.trim(),
      business_type: values.business_type,
      business_name: values.business_name.trim(),
      branch_ifsc_code: values.branch_ifsc_code.trim().toUpperCase(),
      beneficiary_name: values.beneficiary_name.trim(),
      phone: normalizePhone(values.phone),
      business_category: values.business_category,
      business_subcategory: values.business_subcategory,
      street1: values.street1.trim(),
      street2: values.street2.trim() || null,
      city: values.city.trim(),
      state: values.state.trim(),
      postal_code: values.postal_code.trim(),
    };

    if (existing) {
      save.mutate({
        existing: true,
        input: {
          ...commonInput,
          account_number: values.account_number || undefined,
          pan: values.pan ? values.pan.toUpperCase() : undefined,
        },
      });
      return;
    }

    save.mutate({
      existing: false,
      input: {
        ...commonInput,
        account_number: values.account_number,
        pan: values.pan.toUpperCase(),
      },
    });
  });

  return (
    <div className="payment-account-manager">
      <section className="workspace-panel payment-account-panel">
        <div className="panel-heading">
          <div>
            <span>01 / Settlement account</span>
            <h2>Your payment rail</h2>
          </div>
          <p>
            Invitees pay Threecal securely through Razorpay. Your share is
            transferred automatically to the bank account you add here.
          </p>
        </div>

        <div className="payment-account-stage">
          {account.isLoading && (
            <div className="payment-account-loading">
              <LoaderCircle className="spin" size={18} />
              Loading payment settings
            </div>
          )}
          {account.isError && (
            <StatusMessage>{getErrorMessage(account.error)}</StatusMessage>
          )}

          {!account.isLoading && !account.isError && !account.data && (
            <article className="payment-connect-card">
              <div className="payment-connect-mark" aria-hidden="true">
                <Landmark size={28} />
                <span>INR</span>
              </div>
              <p className="payment-status-label">Not connected</p>
              <h3>Give every booking a destination.</h3>
              <p>
                Complete your account and KYC details once. Razorpay verifies
                your bank account, then paid bookings open automatically.
              </p>
              <ol className="payment-connect-steps">
                <li><span>01</span>Account</li>
                <li><span>02</span>KYC</li>
                <li><span>03</span>Bank</li>
              </ol>
              <button
                className="payment-connect-button"
                onClick={openEditor}
                type="button"
              >
                <Landmark size={16} /> Connect payments
              </button>
            </article>
          )}

          {account.data && (
            <article className="payment-readonly-card">
              <header>
                <div className="payment-account-identity">
                  <span aria-hidden="true"><Landmark size={21} /></span>
                  <div>
                    <p>Settlement account</p>
                    <h3>{account.data.business_name}</h3>
                  </div>
                </div>
                <span className="payment-connected-status">
                  {account.data.payouts_enabled ? <CheckCircle2 size={14} /> : <Clock3 size={14} />}{" "}
                  {activationStatusLabels[account.data.activation_status]}
                </span>
              </header>

              <PayoutStatus
                account={account.data}
                onSync={() => sync.mutate()}
                syncing={sync.isPending}
              />
              {sync.isError && (
                <StatusMessage>{getErrorMessage(sync.error)}</StatusMessage>
              )}

              <div className="payment-detail-groups">
                <section>
                  <p>Account contact</p>
                  <dl>
                    <ReadOnlyDetail
                      icon={UserRound}
                      label="Account name"
                      value={account.data.account_name}
                    />
                    <ReadOnlyDetail
                      icon={AtSign}
                      label="Account email"
                      value={account.data.account_email}
                    />
                    <ReadOnlyDetail
                      icon={Phone}
                      label="Phone"
                      value={account.data.phone ?? "Not provided"}
                    />
                  </dl>
                </section>
                <section>
                  <p>KYC details</p>
                  <dl>
                    <ReadOnlyDetail
                      icon={Building2}
                      label="Business type"
                      value={businessTypeLabel(account.data.business_type)}
                    />
                    <ReadOnlyDetail
                      icon={Building2}
                      label="Business name"
                      value={account.data.business_name}
                    />
                    <ReadOnlyDetail
                      icon={Tags}
                      label="Category"
                      value={categoryLabel(account.data.business_category, account.data.business_subcategory)}
                    />
                    <ReadOnlyDetail
                      icon={IdCard}
                      label="PAN"
                      value={account.data.masked_pan ?? "Not provided"}
                      monospaced
                    />
                    <ReadOnlyDetail
                      icon={MapPin}
                      label="Registered address"
                      value={addressLabel(account.data)}
                    />
                  </dl>
                </section>
                <section>
                  <p>Bank details</p>
                  <dl>
                    <ReadOnlyDetail
                      icon={Landmark}
                      label="Branch IFSC code"
                      value={account.data.branch_ifsc_code}
                      monospaced
                    />
                    <ReadOnlyDetail
                      icon={CreditCard}
                      label="Account number"
                      value={account.data.masked_account_number}
                      monospaced
                    />
                    <ReadOnlyDetail
                      icon={UserRound}
                      label="Beneficiary name"
                      value={account.data.beneficiary_name}
                    />
                  </dl>
                </section>
              </div>

              <footer>
                <span><ShieldCheck size={15} /> Details are read-only</span>
                <button
                  className="payment-edit-button"
                  onClick={openEditor}
                  type="button"
                >
                  <Pencil size={14} /> Edit details
                </button>
              </footer>
            </article>
          )}
        </div>
      </section>

      <Dialog.Root onOpenChange={handleOpenChange} open={editorOpen}>
        <Dialog.Portal>
          <Dialog.Backdrop className="profile-dialog-backdrop" />
          <Dialog.Viewport className="profile-dialog-viewport payment-dialog-viewport">
            <Dialog.Popup className="profile-dialog-popup payment-dialog-popup">
              <div className="profile-dialog-header">
                <div>
                  <p className="kicker kicker-dark">
                    {account.data ? "Edit payment details" : "Connect payments"}
                  </p>
                  <Dialog.Title>
                    {account.data
                      ? "Update your settlement account"
                      : "Where should payments land?"}
                  </Dialog.Title>
                  <Dialog.Description>
                    Razorpay uses these account, KYC, and bank details to
                    verify and pay out your share of each booking.
                  </Dialog.Description>
                </div>
                <Dialog.Close
                  aria-label="Close payment details dialog"
                  className="profile-dialog-close"
                  disabled={save.isPending}
                >
                  <X size={18} />
                </Dialog.Close>
              </div>

              <form
                className="profile-dialog-form payment-dialog-form"
                noValidate
                onSubmit={onSubmit}
              >
                <p className="payment-form-section">
                  <span>01</span> Account contact
                </p>
                <label>
                  <span>Account name</span>
                  <input
                    autoComplete="name"
                    placeholder="Aarav Mehta"
                    {...register("account_name")}
                  />
                  {errors.account_name && (
                    <small className="field-error">
                      {errors.account_name.message}
                    </small>
                  )}
                </label>
                <label>
                  <span>Account email</span>
                  <input
                    autoComplete="email"
                    readOnly={lockedIdentity}
                    inputMode="email"
                    placeholder="accounts@business.com"
                    type="email"
                    {...register("account_email")}
                  />
                  {lockedIdentity && (
                    <small className="field-hint">Contact support to change this.</small>
                  )}
                  {errors.account_email && (
                    <small className="field-error">
                      {errors.account_email.message}
                    </small>
                  )}
                </label>
                <label>
                  <span>Phone</span>
                  <input
                    autoComplete="tel"
                    inputMode="tel"
                    maxLength={20}
                    placeholder="9876543210"
                    type="tel"
                    {...register("phone")}
                  />
                  {errors.phone && (
                    <small className="field-error">{errors.phone.message}</small>
                  )}
                </label>

                <p className="payment-form-section">
                  <span>02</span> KYC details
                </p>
                <label>
                  <span>Business type</span>
                  <Controller
                    control={control}
                    name="business_type"
                    render={({ field }) => (
                      <Select
                        disabled={lockedIdentity}
                        inputRef={field.ref}
                        name={field.name}
                        onValueChange={field.onChange}
                        value={field.value}
                      >
                        <SelectTrigger
                          aria-invalid={Boolean(errors.business_type)}
                          aria-label="Business type"
                          className="dashboard-select-trigger"
                          onBlur={field.onBlur}
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="dashboard-select-content">
                          {businessTypeOptions.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                  {errors.business_type && (
                    <small className="field-error">
                      {errors.business_type.message}
                    </small>
                  )}
                </label>
                <label>
                  <span>Legal business name</span>
                  <input
                    autoComplete="organization"
                    placeholder="Mehta Consulting"
                    {...register("business_name")}
                  />
                  {errors.business_name && (
                    <small className="field-error">
                      {errors.business_name.message}
                    </small>
                  )}
                </label>
                <label>
                  <span>Business category</span>
                  <Controller
                    control={control}
                    name="business_category"
                    render={({ field }) => (
                      <Select
                        inputRef={field.ref}
                        name={field.name}
                        onValueChange={(value) => {
                          field.onChange(value);
                          setValue("business_subcategory", "");
                        }}
                        value={field.value || null}
                      >
                        <SelectTrigger
                          aria-invalid={Boolean(errors.business_category)}
                          aria-label="Business category"
                          className="dashboard-select-trigger"
                          onBlur={field.onBlur}
                        >
                          <SelectValue placeholder="Choose a category">
                            {(value: string | null) =>
                              businessCategoryOptions.find((option) => option.value === value)?.label ?? "Choose a category"
                            }
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent className="dashboard-select-content">
                          {businessCategoryOptions.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                  {errors.business_category && (
                    <small className="field-error">
                      {errors.business_category.message}
                    </small>
                  )}
                </label>
                <label>
                  <span>Sub-category</span>
                  <Controller
                    control={control}
                    name="business_subcategory"
                    render={({ field }) => (
                      <Select
                        disabled={!subcategoryOptions.length}
                        inputRef={field.ref}
                        name={field.name}
                        onValueChange={field.onChange}
                        value={field.value || null}
                      >
                        <SelectTrigger
                          aria-invalid={Boolean(errors.business_subcategory)}
                          aria-label="Business sub-category"
                          className="dashboard-select-trigger"
                          onBlur={field.onBlur}
                        >
                          <SelectValue placeholder="Choose a sub-category">
                            {(value: string | null) =>
                              subcategoryOptions.find((option) => option.value === value)?.label ?? "Choose a sub-category"
                            }
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent className="dashboard-select-content">
                          {subcategoryOptions.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                  {errors.business_subcategory && (
                    <small className="field-error">
                      {errors.business_subcategory.message}
                    </small>
                  )}
                </label>
                <label className="payment-beneficiary-field">
                  <span>{personalPan ? "Owner's PAN" : "Business PAN"}</span>
                  <input
                    autoCapitalize="characters"
                    autoComplete="off"
                    maxLength={10}
                    placeholder={account.data?.masked_pan ?? (personalPan ? "ABCPE1234F" : "AAACM1234C")}
                    {...register("pan")}
                  />
                  <small className="field-hint">
                    {account.data?.masked_pan
                      ? "Leave blank to keep the saved PAN."
                      : personalPan
                        ? "Your personal PAN (4th character is P)."
                        : "The PAN issued to the business."}
                  </small>
                  {errors.pan && (
                    <small className="field-error">{errors.pan.message}</small>
                  )}
                </label>

                <p className="payment-form-section">
                  <span>03</span> Registered address
                </p>
                <label>
                  <span>Street address</span>
                  <input autoComplete="address-line1" placeholder="507, Koramangala 1st block" {...register("street1")} />
                  {errors.street1 && (
                    <small className="field-error">{errors.street1.message}</small>
                  )}
                </label>
                <label>
                  <span>Address line 2 <small>(optional)</small></span>
                  <input autoComplete="address-line2" placeholder="MG Road" {...register("street2")} />
                  {errors.street2 && (
                    <small className="field-error">{errors.street2.message}</small>
                  )}
                </label>
                <label>
                  <span>City</span>
                  <input autoComplete="address-level2" placeholder="Bengaluru" {...register("city")} />
                  {errors.city && (
                    <small className="field-error">{errors.city.message}</small>
                  )}
                </label>
                <label>
                  <span>State</span>
                  <input autoComplete="address-level1" placeholder="Karnataka" {...register("state")} />
                  {errors.state && (
                    <small className="field-error">{errors.state.message}</small>
                  )}
                </label>
                <label>
                  <span>PIN code</span>
                  <input autoComplete="postal-code" inputMode="numeric" maxLength={6} placeholder="560034" {...register("postal_code")} />
                  {errors.postal_code && (
                    <small className="field-error">{errors.postal_code.message}</small>
                  )}
                </label>

                <p className="payment-form-section">
                  <span>04</span> Bank details
                </p>
                <label>
                  <span>Branch IFSC code</span>
                  <input
                    autoCapitalize="characters"
                    autoComplete="off"
                    maxLength={11}
                    placeholder="HDFC0001234"
                    {...register("branch_ifsc_code")}
                  />
                  {errors.branch_ifsc_code && (
                    <small className="field-error">
                      {errors.branch_ifsc_code.message}
                    </small>
                  )}
                </label>
                <label>
                  <span>Account number</span>
                  <input
                    autoComplete="off"
                    inputMode="numeric"
                    maxLength={34}
                    placeholder={
                      account.data
                        ? account.data.masked_account_number
                        : "Enter bank account number"
                    }
                    type="password"
                    {...register("account_number")}
                  />
                  <small className="field-hint">
                    {account.data
                      ? "Leave blank to keep the saved account number."
                      : ""}
                  </small>
                  {errors.account_number && (
                    <small className="field-error">
                      {errors.account_number.message}
                    </small>
                  )}
                </label>
                <label className="payment-beneficiary-field">
                  <span>Beneficiary name</span>
                  <input
                    autoComplete="name"
                    placeholder="Name registered with the bank"
                    {...register("beneficiary_name")}
                  />
                  {errors.beneficiary_name && (
                    <small className="field-error">
                      {errors.beneficiary_name.message}
                    </small>
                  )}
                </label>

                <div className="payment-security-note">
                  <LockKeyhole aria-hidden="true" size={17} />
                  <p>
                    Your bank account number and PAN are encrypted before
                    storage, shared only with Razorpay for verification, and
                    returned here only in masked form. By saving you accept
                    Razorpay&apos;s Route terms for payouts.
                  </p>
                </div>
                {save.isError && (
                  <StatusMessage>{getErrorMessage(save.error)}</StatusMessage>
                )}

                <div className="profile-dialog-actions payment-dialog-actions">
                  <Dialog.Close
                    className="profile-dialog-cancel"
                    disabled={save.isPending}
                  >
                    Cancel
                  </Dialog.Close>
                  <button
                    className="save-button"
                    disabled={save.isPending}
                    type="submit"
                  >
                    {save.isPending ? (
                      <LoaderCircle className="spin" size={16} />
                    ) : (
                      <Check size={16} />
                    )}
                    {save.isPending
                      ? "Saving"
                      : account.data
                        ? "Save changes"
                        : "Connect account"}
                  </button>
                </div>
              </form>
            </Dialog.Popup>
          </Dialog.Viewport>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
