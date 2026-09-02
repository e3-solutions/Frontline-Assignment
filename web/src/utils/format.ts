const DATE_OPTIONS: Intl.DateTimeFormatOptions = {
   month: "short",
   day: "numeric",
   hour: "numeric",
   minute: "2-digit",
};

const DATE_ONLY_OPTIONS: Intl.DateTimeFormatOptions = {
   month: "short",
   day: "numeric",
};

export const formatDateTime = (value?: string) => {
   if (!value) return "—";
   return new Date(value).toLocaleString(undefined, DATE_OPTIONS);
};

export const formatDate = (value?: string) => {
   if (!value) return "—";
   return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, DATE_ONLY_OPTIONS);
};

export const calculateDuration = (start: string, end?: string) => {
   if (!end) return "In progress";
   const startTime = new Date(start).getTime();
   const endTime = new Date(end).getTime();
   const diffMinutes = Math.max(Math.round((endTime - startTime) / 60000), 1);
   return `${diffMinutes} min`;
};

export const formatPhone = (country: string, number: string) => `${country} ${number}`;

export const formatCurrency = (
   value?: number | null,
   { minimumFractionDigits = 0, maximumFractionDigits = 0 }: Intl.NumberFormatOptions = {}
) => {
   if (value === undefined || value === null || Number.isNaN(value) || value <= 0) {
      return "—";
   }

   return `$${value.toLocaleString(undefined, {
      minimumFractionDigits,
      maximumFractionDigits,
   })}`;
};

export const calculateAverageRate = (rates: number[]) => {
   if (rates.length === 0) return "—";
   const totalRate = rates.reduce((acc, rate) => acc + rate, 0);
   if (totalRate <= 0) return "—";
   const average = totalRate / rates.length;
   return `${formatCurrency(average, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} / mi`;
};
