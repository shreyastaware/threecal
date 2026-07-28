"use client";

import { Dialog } from "@base-ui/react/dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  ImageIcon,
  ImagePlus,
  LoaderCircle,
  Pencil,
  UploadCloud,
  X,
} from "lucide-react";
import posthog from "posthog-js";
import {
  type DragEvent,
  type ChangeEvent,
  useEffect,
  useId,
  useState,
} from "react";

import { CURRENT_USER_KEY } from "@/components/providers/auth-provider";
import type { User } from "@/features/auth/types/auth";
import { StatusMessage } from "@/features/dashboard/components/status-message";
import { schedulingApi } from "@/features/scheduling/api";
import { profileImageSchema } from "@/features/scheduling/schemas";
import { getErrorMessage } from "@/lib/api/client";

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

export function ProfileImageField({ user }: { user: User }) {
  const inputId = useId();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const upload = useMutation({
    mutationFn: schedulingApi.uploadAvatar,
    onSuccess: (updated) => {
      queryClient.setQueryData(CURRENT_USER_KEY, updated);
      posthog.capture("profile_image_uploaded", {
        content_type: file?.type,
        size_bytes: file?.size,
      });
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
      setFile(null);
      setOpen(false);
    },
  });

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function chooseFile(candidate: File | null) {
    upload.reset();
    setValidationError(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setFile(null);
    if (!candidate) return;

    const result = profileImageSchema.safeParse(candidate);
    if (!result.success) {
      setValidationError(
        result.error.issues[0]?.message ?? "Choose a valid image",
      );
      return;
    }

    setFile(result.data);
    setPreviewUrl(URL.createObjectURL(result.data));
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    chooseFile(event.target.files?.[0] ?? null);
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    chooseFile(event.dataTransfer.files[0] ?? null);
  }

  function handleOpenChange(nextOpen: boolean) {
    if (upload.isPending) return;
    setOpen(nextOpen);
    if (!nextOpen) {
      chooseFile(null);
      setIsDragging(false);
    }
  }

  const visibleImage = previewUrl ?? user.avatar_url;

  return (
    <>
      <article className="profile-field-row">
        <ImageIcon aria-hidden="true" size={17} />
        <div>
          <span>Profile image</span>
          <p>{user.avatar_url ? "Photo added" : "Not added yet"}</p>
        </div>
        <button
          aria-label="Edit profile image"
          className="profile-edit-button"
          onClick={() => setOpen(true)}
          type="button"
        >
          <Pencil size={14} /> Edit
        </button>
      </article>

      <Dialog.Root onOpenChange={handleOpenChange} open={open}>
        <Dialog.Portal>
          <Dialog.Backdrop className="profile-dialog-backdrop" />
          <Dialog.Viewport className="profile-dialog-viewport">
            <Dialog.Popup className="profile-dialog-popup profile-image-dialog">
              <div className="profile-dialog-header">
                <div>
                  <p className="kicker kicker-dark">Profile detail</p>
                  <Dialog.Title>Upload your profile image</Dialog.Title>
                  <Dialog.Description>
                    We crop it to a square, optimize it for the web, and store
                    it securely. JPEG, PNG, or WebP up to 5 MB.
                  </Dialog.Description>
                </div>
                <Dialog.Close
                  aria-label="Close image dialog"
                  className="profile-dialog-close"
                  disabled={upload.isPending}
                >
                  <X size={18} />
                </Dialog.Close>
              </div>

              <div className="profile-image-workspace">
                <div className="profile-image-preview">
                  {visibleImage ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img alt="Profile preview" src={visibleImage} />
                  ) : (
                    <span>{initials(user.full_name)}</span>
                  )}
                  {file && (
                    <span className="profile-image-ready">
                      <Check size={12} /> Ready
                    </span>
                  )}
                </div>

                <label
                  className={
                    isDragging
                      ? "profile-image-dropzone is-dragging"
                      : "profile-image-dropzone"
                  }
                  htmlFor={inputId}
                  onDragEnter={(event) => {
                    event.preventDefault();
                    setIsDragging(true);
                  }}
                  onDragLeave={() => setIsDragging(false)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={handleDrop}
                >
                  {file ? <ImagePlus size={22} /> : <UploadCloud size={22} />}
                  <strong>{file ? file.name : "Drop an image here"}</strong>
                  <span>
                    {file
                      ? `${(file.size / 1024 / 1024).toFixed(2)} MB · Click to replace`
                      : "or click to browse your device"}
                  </span>
                  <input
                    accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                    id={inputId}
                    onChange={handleInputChange}
                    type="file"
                  />
                </label>
              </div>

              {validationError && (
                <StatusMessage>{validationError}</StatusMessage>
              )}
              {upload.isError && (
                <StatusMessage>{getErrorMessage(upload.error)}</StatusMessage>
              )}

              <div className="profile-dialog-actions">
                <Dialog.Close
                  className="profile-dialog-cancel"
                  disabled={upload.isPending}
                >
                  Cancel
                </Dialog.Close>
                <button
                  className="save-button"
                  disabled={!file || upload.isPending}
                  onClick={() => file && upload.mutate(file)}
                  type="button"
                >
                  {upload.isPending ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : (
                    <UploadCloud size={16} />
                  )}
                  {upload.isPending ? "Processing" : "Upload image"}
                </button>
              </div>
            </Dialog.Popup>
          </Dialog.Viewport>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
