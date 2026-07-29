"use client";

import { Dialog } from "@base-ui/react/dialog";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AtSign,
  Building2,
  Check,
  CheckCircle2,
  CreditCard,
  Landmark,
  LoaderCircle,
  LockKeyhole,
  Pencil,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import posthog from "posthog-js";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import {
  paymentsApi,
  type PaymentAccount,
  type PaymentAccountCreate,
  type PaymentAccountUpdate,
} from "@/features/payments/api";
import {
  businessTypeOptions,
  paymentAccountFormSchema,
  type PaymentAccountFormValues,
} from "@/features/payments/schemas";
import { getErrorMessage } from "@/lib/api/client";

const PAYMENT_ACCOUNT_KEY = ["payments", "account"] as const;

function formValues(
  account: PaymentAccount | null | undefined,
  user: { full_name: string; email: string } | null,
): PaymentAccountFormValues {
  return {
    account_name: account?.account_name ?? user?.full_name ?? "",
    account_email: account?.account_email ?? user?.email ?? "",
    business_type: account?.business_type ?? "individual",
    business_name: account?.business_name ?? "",
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

export function PaymentAccountManager() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [editorOpen, setEditorOpen] = useState(false);
  const account = useQuery({
    queryKey: PAYMENT_ACCOUNT_KEY,
    queryFn: paymentsApi.getAccount,
    enabled: Boolean(user),
  });
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
        { business_type: updated.business_type },
      );
      setEditorOpen(false);
      reset(formValues(updated, user));
    },
  });
  const {
    register,
    reset,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<PaymentAccountFormValues>({
    resolver: zodResolver(paymentAccountFormSchema),
    defaultValues: formValues(null, user),
  });

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

    const commonInput = {
      account_name: values.account_name.trim(),
      account_email: values.account_email.trim(),
      business_type: values.business_type,
      business_name: values.business_name.trim(),
      branch_ifsc_code: values.branch_ifsc_code.trim().toUpperCase(),
      beneficiary_name: values.beneficiary_name.trim(),
    };

    if (existing) {
      save.mutate({
        existing: true,
        input: {
          ...commonInput,
          account_number: values.account_number || undefined,
        },
      });
      return;
    }

    save.mutate({
      existing: false,
      input: {
        ...commonInput,
        account_number: values.account_number,
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
            Add the account that should receive booking payments. Your details
            stay locked until you explicitly choose to edit them.
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
                Complete your account and KYC details once. You can review them
                here any time and reopen the form when something changes.
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
                  <CheckCircle2 size={14} /> Connected
                </span>
              </header>

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
                    Add the account contact, KYC, and bank details used for
                    settlement.
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
                    inputMode="email"
                    placeholder="accounts@business.com"
                    type="email"
                    {...register("account_email")}
                  />
                  {errors.account_email && (
                    <small className="field-error">
                      {errors.account_email.message}
                    </small>
                  )}
                </label>

                <p className="payment-form-section">
                  <span>02</span> KYC details
                </p>
                <label>
                  <span>Business type</span>
                  <select {...register("business_type")}>
                    {businessTypeOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                  {errors.business_type && (
                    <small className="field-error">
                      {errors.business_type.message}
                    </small>
                  )}
                </label>
                <label>
                  <span>Business name</span>
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

                <p className="payment-form-section">
                  <span>03</span> Bank details
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
                    Your bank account number is encrypted before storage and
                    returned only in masked form.
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
