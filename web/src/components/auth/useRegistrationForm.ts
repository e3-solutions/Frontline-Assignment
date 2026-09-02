"use client";

import { useState, useCallback } from "react";

interface RegistrationForm {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
  showPassword: boolean;
  isLoading: boolean;
}

export function useRegistrationForm(initialEmail = "") {
  const [form, setForm] = useState<RegistrationForm>({
    fullName: "",
    email: initialEmail,
    password: "",
    confirmPassword: "",
    showPassword: false,
    isLoading: false,
  });

  const updateField = useCallback(<K extends keyof RegistrationForm>(
    field: K,
    value: RegistrationForm[K]
  ) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  }, []);

  const toggleShowPassword = useCallback(() => {
    setForm((prev) => ({ ...prev, showPassword: !prev.showPassword }));
  }, []);

  const setLoading = useCallback((isLoading: boolean) => {
    setForm((prev) => ({ ...prev, isLoading }));
  }, []);

  const setEmail = useCallback((email: string) => {
    setForm((prev) => ({ ...prev, email }));
  }, []);

  const validatePasswords = useCallback((): boolean => {
    return form.password === form.confirmPassword;
  }, [form.password, form.confirmPassword]);

  return {
    form,
    updateField,
    toggleShowPassword,
    setLoading,
    setEmail,
    validatePasswords,
  };
}
