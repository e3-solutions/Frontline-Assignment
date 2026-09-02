"use client";

import React, { useState } from "react";
import { Button, Checkbox, CloseIcon, DatePicker, DollarIcon, FormField, Input, Notification, Textarea } from "@e3-solutions/ui";
import PhoneInput from "@/src/inputs/PhoneInput";
import { createLoad } from "@/src/api/loads";
import type { LoadApiRequest } from "@/src/types/dashboard";

const emptyForm: LoadApiRequest = {
   load_id: "",
   contact_phone: "",
   country_code: "+1",
   transfer_call_to: "",
   transfer_country_code: "+1",
   broker_name: "",
   origin_location: "",
   destination_location: "",
   pickup_time: "",
   delivery_time: "",
   requirements: "",
   tracker_required: false,
   broker_initial_offer: "",
   broker_target_rate: "",
   broker_max_rate: "",
   company_name: "",
   customer_name: "",
};

function parseDate(value: string): Date | null {
   if (!value) return null;
   const d = new Date(value);
   return isNaN(d.getTime()) ? null : d;
}

function toDatetimeLocal(date: Date | null): string {
   if (!date) return "";
   const pad = (n: number) => String(n).padStart(2, "0");
   return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

type NegotiationFormProps = {
   onClose?: () => void;
};

export default function NegotiationForm({ onClose }: NegotiationFormProps) {
   const [formData, setFormData] = useState<LoadApiRequest>({ ...emptyForm });
   const [isSubmitting, setIsSubmitting] = useState(false);
   const [notification, setNotification] = useState<{
      type: "success" | "error";
      message: string;
   } | null>(null);

   const update = (field: keyof LoadApiRequest, value: string | boolean) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
   };

   const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const { name, value } = e.target;
      if (name === "load_id" && value && !/^\d*$/.test(value)) return;
      update(name as keyof LoadApiRequest, value);
   };

   const fillMockData = () => {
      const now = new Date();
      const pickupTime = new Date(now.getTime() + 24 * 60 * 60 * 1000);
      const deliveryTime = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000);

      setFormData({
         load_id: String(Math.floor(Math.random() * 10000)),
         contact_phone: "(555) 123-4567",
         country_code: "+1",
         transfer_call_to: "(555) 987-6543",
         transfer_country_code: "+1",
         broker_name: "John Doe Logistics",
         origin_location: "Los Angeles, CA",
         destination_location: "New York, NY",
         pickup_time: toDatetimeLocal(pickupTime),
         delivery_time: toDatetimeLocal(deliveryTime),
         requirements: "Refrigerated truck, liftgate required",
         tracker_required: true,
         broker_initial_offer: "2500",
         broker_target_rate: "3000",
         broker_max_rate: "3500",
         company_name: "ABC Freight Inc",
         customer_name: "Jane Smith",
      });
   };

   const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      setIsSubmitting(true);

      createLoad(formData)
         .then(() => {
            setNotification({ type: "success", message: "Load created successfully!" });
            setFormData({ ...emptyForm });
         })
         .catch((error) => {
            setNotification({
               type: "error",
               message: error.message || "Failed to create load. Please try again.",
            });
         })
         .finally(() => setIsSubmitting(false));
   };

   return (
      <>
         {notification && (
            <Notification
               type={notification.type}
               message={notification.message}
               onClose={() => setNotification(null)}
            />
         )}
         <form
            onSubmit={handleSubmit}
            className="w-full px-6 py-6 sm:px-8"
         >
            {/* Header */}
            <header className="mb-8 flex items-start justify-between gap-4">
               <div>
                  <h1 className="text-3xl font-semibold text-[color:var(--e3-text-strong)] e3-font-heading">
                     Create Load
                  </h1>
                  <p className="mt-1.5 max-w-xl text-sm text-[color:var(--e3-text-muted)] e3-font-body">
                     Set up a new load for the negotiation agent.
                  </p>
               </div>
               <div className="flex items-center gap-3">
                  {process.env.NEXT_PUBLIC_ENVIRONMENT !== "prod" && (
                     <Button type="button" variant="secondary" size="sm" onClick={fillMockData}>
                        Fill Mock Data
                     </Button>
                  )}
                  {onClose && (
                     <button
                        type="button"
                        onClick={onClose}
                        className="cursor-pointer rounded-2xl border border-[color:var(--e3-border-soft)] bg-[color:var(--e3-surface-soft)] p-2.5 text-[color:var(--e3-text-muted)] transition-all hover:border-[color:var(--e3-border-strong)] hover:bg-[color:var(--e3-surface-alt)] hover:text-[color:var(--e3-text-strong)]"
                        aria-label="Close"
                     >
                        <CloseIcon className="h-5 w-5" />
                     </button>
                  )}
               </div>
            </header>

            {/* ── Identifiers ── */}
            <section className="pb-6 mb-6 border-b border-[color:var(--e3-divider)]">
               <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-[color:var(--e3-text-soft)] e3-font-mono">
                  Identifiers
               </h2>
               <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
                  <FormField label="Load ID" htmlFor="load_id" required>
                     <Input
                        id="load_id"
                        name="load_id"
                        value={formData.load_id}
                        placeholder="8171"
                        required
                        inputMode="numeric"
                        onChange={handleInputChange}
                     />
                  </FormField>
                  <FormField label="Company" htmlFor="company_name" required>
                     <Input
                        id="company_name"
                        name="company_name"
                        value={formData.company_name}
                        placeholder="ABC Freight Inc"
                        required
                        onChange={handleInputChange}
                     />
                  </FormField>
                  <FormField label="Customer" htmlFor="customer_name" required>
                     <Input
                        id="customer_name"
                        name="customer_name"
                        value={formData.customer_name}
                        placeholder="Jane Smith"
                        required
                        onChange={handleInputChange}
                     />
                  </FormField>
                  <FormField label="Broker" htmlFor="broker_name" required>
                     <Input
                        id="broker_name"
                        name="broker_name"
                        value={formData.broker_name}
                        placeholder="John Doe Logistics"
                        required
                        onChange={handleInputChange}
                     />
                  </FormField>
               </div>
            </section>

            {/* ── Contact ── */}
            <section className="pb-6 mb-6 border-b border-[color:var(--e3-divider)]">
               <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-[color:var(--e3-text-soft)] e3-font-mono">
                  Contact
               </h2>
               <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
                  <PhoneInput
                     label="Contact Phone"
                     name="contact_phone"
                     value={formData.contact_phone}
                     countryCode={formData.country_code}
                     required
                     onChange={handleInputChange}
                     onCountryCodeChange={(code) => update("country_code", code)}
                  />
                  <PhoneInput
                     label="Transfer Call To"
                     name="transfer_call_to"
                     value={formData.transfer_call_to}
                     countryCode={formData.transfer_country_code}
                     required
                     onChange={handleInputChange}
                     onCountryCodeChange={(code) => update("transfer_country_code", code)}
                  />
               </div>
            </section>

            {/* ── Route ── */}
            <section className="pb-6 mb-6 border-b border-[color:var(--e3-divider)]">
               <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-[color:var(--e3-text-soft)] e3-font-mono">
                  Route
               </h2>
               <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
                  <FormField label="Origin" htmlFor="origin_location" required>
                     <Input
                        id="origin_location"
                        name="origin_location"
                        value={formData.origin_location}
                        placeholder="Los Angeles, CA"
                        required
                        onChange={handleInputChange}
                     />
                  </FormField>
                  <FormField label="Destination" htmlFor="destination_location" required>
                     <Input
                        id="destination_location"
                        name="destination_location"
                        value={formData.destination_location}
                        placeholder="New York, NY"
                        required
                        onChange={handleInputChange}
                     />
                  </FormField>
                  <FormField label="Pickup Date" required>
                     <DatePicker
                        value={parseDate(formData.pickup_time)}
                        onChange={(date) => update("pickup_time", toDatetimeLocal(date))}
                        placeholder="Select pickup date"
                        minDate={new Date()}
                     />
                  </FormField>
                  <FormField label="Delivery Date" required>
                     <DatePicker
                        value={parseDate(formData.delivery_time)}
                        onChange={(date) => update("delivery_time", toDatetimeLocal(date))}
                        placeholder="Select delivery date"
                        minDate={parseDate(formData.pickup_time) ?? new Date()}
                     />
                  </FormField>
                  <div className="flex items-end pb-1">
                     <Checkbox
                        label="Tracker Required"
                        checked={formData.tracker_required}
                        onCheckedChange={(checked) => update("tracker_required", checked)}
                     />
                  </div>
               </div>
               <div className="mt-4">
                  <FormField label="Requirements" htmlFor="requirements">
                     <Textarea
                        id="requirements"
                        name="requirements"
                        value={formData.requirements}
                        placeholder="Refrigerated truck, liftgate required, hazmat certified..."
                        onChange={handleInputChange}
                        resize="vertical"
                     />
                  </FormField>
               </div>
            </section>

            {/* ── Pricing ── */}
            <section className="pb-6 mb-6 border-b border-[color:var(--e3-divider)]">
               <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.12em] text-[color:var(--e3-text-soft)] e3-font-mono">
                  Pricing
               </h2>
               <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-3">
                  <FormField label="Initial Offer" htmlFor="broker_initial_offer" required>
                     <Input
                        id="broker_initial_offer"
                        name="broker_initial_offer"
                        type="number"
                        value={formData.broker_initial_offer}
                        placeholder="2,500"
                        required
                        inputMode="decimal"
                        min={0}
                        step="0.01"
                        onChange={handleInputChange}
                        iconLeft={<DollarIcon className="h-4 w-4" />}
                     />
                  </FormField>
                  <FormField label="Target Rate" htmlFor="broker_target_rate" required>
                     <Input
                        id="broker_target_rate"
                        name="broker_target_rate"
                        type="number"
                        value={formData.broker_target_rate}
                        placeholder="3,000"
                        required
                        inputMode="decimal"
                        min={0}
                        step="0.01"
                        onChange={handleInputChange}
                        iconLeft={<DollarIcon className="h-4 w-4" />}
                     />
                  </FormField>
                  <FormField label="Max Rate" htmlFor="broker_max_rate" required>
                     <Input
                        id="broker_max_rate"
                        name="broker_max_rate"
                        type="number"
                        value={formData.broker_max_rate}
                        placeholder="3,500"
                        required
                        inputMode="decimal"
                        min={0}
                        step="0.01"
                        onChange={handleInputChange}
                        iconLeft={<DollarIcon className="h-4 w-4" />}
                     />
                  </FormField>
               </div>
            </section>

            {/* Submit */}
            <div className="flex justify-end">
               <Button type="submit" variant="primary" size="lg" loading={isSubmitting}>
                  Create Load
               </Button>
            </div>
         </form>
      </>
   );
}
