"use client";

import { useMutation } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useState } from "react";

import type { User } from "@/features/auth/types/auth";
import { schedulingApi } from "@/features/scheduling/api";

export function ProfileEditor({ user }: { user: User }) {
  const [form, setForm] = useState({ full_name: user.full_name, username: user.username ?? "", timezone: user.timezone, bio: user.bio ?? "" });
  const save = useMutation({ mutationFn: schedulingApi.updateProfile });
  return <section className="workspace-panel profile-panel">
    <div className="panel-heading"><div><span>01 / Profile</span><h2>Your public desk</h2></div><p>This becomes the introduction on your booking page.</p></div>
    <div className="profile-form"><label><span>Full name</span><input value={form.full_name} onChange={(e) => setForm({...form, full_name: e.target.value})}/></label><label><span>Booking URL</span><div className="url-input"><small>threecal.com/</small><input value={form.username} onChange={(e) => setForm({...form, username: e.target.value.toLowerCase()})}/></div></label><label><span>Timezone</span><input value={form.timezone} onChange={(e) => setForm({...form, timezone: e.target.value})}/></label><label className="bio-field"><span>Short bio</span><textarea value={form.bio} onChange={(e) => setForm({...form, bio: e.target.value})}/></label></div>
    <button className="save-button" onClick={() => save.mutate(form)}><Check size={16}/> {save.isSuccess ? "Profile saved" : "Save profile"}</button>
  </section>;
}
