"use client";

import { PlusIcon, TriangleAlertIcon } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { NoProjectState } from "@/components/no-project-state";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/label";
import { SimpleSelect } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ErrorState } from "@/components/error-state";
import { Surface, SurfaceHeader } from "@/components/surface";
import { errorMessage } from "@/lib/api/errors";
import type { MaskingMethod } from "@/lib/api/types";
import { categoryLabel, methodLabel } from "@/lib/format";
import { knownCategories, MASKING_METHODS, unmaskedRequiredCategories } from "@/lib/policy";
import { useProjectStore } from "@/lib/project-store";

import { usePolicy, useUpdatePolicy } from "../api";
import { RecognizersPanel } from "./recognizers-panel";

export function PoliciesScreen() {
  const projectId = useProjectStore((s) => s.selectedProjectId);
  const policy = usePolicy(projectId ?? undefined);
  const update = useUpdatePolicy(projectId ?? undefined);

  const [required, setRequired] = React.useState<string[]>([]);
  const [methods, setMethods] = React.useState<Record<string, string>>({});
  const [partialMaskReveal, setPartialMaskReveal] = React.useState("4");
  const [confidenceThreshold, setConfidenceThreshold] = React.useState("0.6");
  const [retentionDays, setRetentionDays] = React.useState("90");
  const [customCategory, setCustomCategory] = React.useState("");

  React.useEffect(() => {
    if (!policy.data) return;
    setRequired(policy.data.required_categories);
    setMethods(policy.data.masking_method);
    setPartialMaskReveal(String(policy.data.partial_mask_reveal));
    setConfidenceThreshold(String(policy.data.confidence_threshold));
    setRetentionDays(String(policy.data.retention_days));
  }, [policy.data]);

  if (!projectId) {
    return (
      <div>
        <PageHeader title="Policies" description="How this project detects, scores and protects PII." />
        <Surface>
          <NoProjectState />
        </Surface>
      </div>
    );
  }

  if (policy.isError) {
    return (
      <div>
        <PageHeader title="Policies" description="How this project detects, scores and protects PII." />
        <Surface>
          <ErrorState error={policy.error} onRetry={() => void policy.refetch()} />
        </Surface>
      </div>
    );
  }

  const allCategories = Array.from(new Set([...knownCategories(), ...Object.keys(methods), ...required]));
  const blocked = unmaskedRequiredCategories({ requiredCategories: required, maskingMethod: methods });

  function toggleCategory(category: string) {
    setRequired((prev) => (prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category]));
  }

  function setMethod(category: string, method: string) {
    setMethods((prev) => ({ ...prev, [category]: method }));
  }

  function addCustomCategory() {
    const c = customCategory.trim().toLowerCase().replace(/\s+/g, "_");
    if (!c) return;
    if (!allCategories.includes(c)) setMethods((prev) => ({ ...prev, [c]: prev[c] ?? "" }));
    setCustomCategory("");
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (blocked.length > 0) {
      toast.error(`Set a masking method for: ${blocked.map(categoryLabel).join(", ")} before saving.`);
      return;
    }
    const pmr = Number(partialMaskReveal);
    const ct = Number(confidenceThreshold);
    const rd = Number(retentionDays);
    if (!Number.isInteger(pmr) || pmr < 0 || pmr > 32) {
      toast.error("Partial mask reveal must be a whole number from 0 to 32.");
      return;
    }
    if (!Number.isFinite(ct) || ct < 0 || ct > 1) {
      toast.error("Confidence threshold must be between 0 and 1.");
      return;
    }
    if (!Number.isInteger(rd) || rd < 1 || rd > 3650) {
      toast.error("Retention days must be a whole number from 1 to 3650.");
      return;
    }
    // Only MASKING_METHODS values are ever written into `methods` by setMethod, via the
    // SimpleSelect options below, so this cast is safe.
    const masking_method = Object.fromEntries(Object.entries(methods).filter(([, v]) => !!v)) as Record<string, MaskingMethod>;
    update.mutate(
      { required_categories: required, masking_method, partial_mask_reveal: pmr, confidence_threshold: ct, retention_days: rd },
      {
        onSuccess: () => toast.success("Policy saved."),
        onError: (err) => toast.error(errorMessage(err)),
      },
    );
  }

  return (
    <div>
      <PageHeader title="Policies" description="How this project detects, scores and protects PII." />

      <Tabs defaultValue="policy">
        <TabsList>
          <TabsTrigger value="policy">Policy</TabsTrigger>
          <TabsTrigger value="recognizers">Custom recognizers</TabsTrigger>
        </TabsList>

        <TabsContent value="policy">
          <form onSubmit={submit} className="space-y-4">
            <Surface>
              <SurfaceHeader
                title="Categories and masking"
                description="Required categories must always have a masking method. A required category with no method is refused by the API."
              />
              <div className="space-y-3 px-5 pb-5">
                {blocked.length > 0 && (
                  <div className="flex gap-2 rounded-lg bg-warning-soft px-3.5 py-2.5 text-[13px] text-warning">
                    <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" />
                    <span>
                      Choose a masking method for: <strong>{blocked.map(categoryLabel).join(", ")}</strong> before saving, or the API
                      will refuse this policy.
                    </span>
                  </div>
                )}
                <div className="divide-y divide-hairline">
                  {allCategories.map((category) => (
                    <div key={category} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                      <label className="flex min-w-0 flex-1 items-center gap-2.5 text-[13px]">
                        <Checkbox checked={required.includes(category)} onCheckedChange={() => toggleCategory(category)} />
                        <span className="truncate text-foreground">{categoryLabel(category)}</span>
                        {required.includes(category) && !methods[category] && (
                          <TriangleAlertIcon className="size-3.5 shrink-0 text-warning" />
                        )}
                      </label>
                      <SimpleSelect
                        value={methods[category] ?? ""}
                        onValueChange={(v) => setMethod(category, v)}
                        options={MASKING_METHODS.map((m) => ({ value: m, label: methodLabel(m) }))}
                        placeholder="No method"
                        size="sm"
                        className="w-44"
                      />
                    </div>
                  ))}
                </div>
                <div className="flex items-end gap-2 pt-2">
                  <Field label="Add a category" htmlFor="custom-category" hint="Free text; the API treats category as a plain string.">
                    <Input id="custom-category" value={customCategory} onChange={(e) => setCustomCategory(e.target.value)} placeholder="loyalty_id" />
                  </Field>
                  <Button type="button" variant="outline" onClick={addCustomCategory}>
                    <PlusIcon />
                    Add
                  </Button>
                </div>
              </div>
            </Surface>

            <Surface>
              <SurfaceHeader title="Thresholds and retention" />
              <div className="grid gap-4 px-5 pb-5 sm:grid-cols-3">
                <Field label="Partial mask reveal" htmlFor="pmr" hint="Characters left visible, 0 to 32.">
                  <Input id="pmr" inputMode="numeric" className="tabular" value={partialMaskReveal} onChange={(e) => setPartialMaskReveal(e.target.value)} />
                </Field>
                <Field label="Confidence threshold" htmlFor="ct" hint="Below this, a finding goes to review instead of being auto-protected, 0 to 1.">
                  <Input id="ct" inputMode="decimal" className="tabular" value={confidenceThreshold} onChange={(e) => setConfidenceThreshold(e.target.value)} />
                </Field>
                <Field label="Retention days" htmlFor="rd" hint="1 to 3650.">
                  <Input id="rd" inputMode="numeric" className="tabular" value={retentionDays} onChange={(e) => setRetentionDays(e.target.value)} />
                </Field>
              </div>
            </Surface>

            <div className="flex justify-end">
              <Button type="submit" size="lg" disabled={update.isPending || policy.isLoading}>
                {update.isPending ? "Saving..." : "Save policy"}
              </Button>
            </div>
          </form>
        </TabsContent>

        <TabsContent value="recognizers">
          <Surface>
            <SurfaceHeader title="Custom recognizers" description="Detect a pattern specific to your data that the built-in detectors do not cover." />
            <div className="px-5 pb-5">
              <RecognizersPanel projectId={projectId} />
            </div>
          </Surface>
        </TabsContent>
      </Tabs>
    </div>
  );
}
