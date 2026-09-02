export function downloadCSV(filename: string, headers: string[], rows: string[][]) {
   const escape = (value: string) => {
      // Prevent CSV injection — prefix formula-triggering characters
      let sanitized = value;
      if (/^[=+\-@\t\r]/.test(sanitized)) {
         sanitized = `'${sanitized}`;
      }
      if (sanitized.includes(",") || sanitized.includes('"') || sanitized.includes("\n")) {
         return `"${sanitized.replace(/"/g, '""')}"`;
      }
      return sanitized;
   };

   const csvContent = [
      headers.map(escape).join(","),
      ...rows.map((row) => row.map(escape).join(",")),
   ].join("\n");

   const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
   const url = URL.createObjectURL(blob);
   const link = document.createElement("a");
   link.href = url;
   link.download = filename;
   link.click();
   URL.revokeObjectURL(url);
}
