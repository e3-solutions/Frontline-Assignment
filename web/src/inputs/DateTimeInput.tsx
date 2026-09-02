import React from "react";

interface DateTimeInputProps {
   label: string;
   name: string;
   value?: string;
   required?: boolean;
   hint?: string;
   onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

const DateTimeInput: React.FC<DateTimeInputProps> = ({
   label,
   name,
   value = "",
   required = false,
   hint,
   onChange,
}) => {
   return (
      <div className="form-group mb-6 relative overflow-visible z-10 min-w-[200px]">
         <label
            htmlFor={name}
            className="block text-sm font-semibold text-gray-800 mb-2 text-left transition-colors duration-300"
         >
            {label}
            {hint && <span className="text-gray-600 font-normal ml-1">{hint}</span>}
         </label>
         <input
            type="datetime-local"
            id={name}
            name={name}
            value={value}
            required={required}
            onChange={onChange}
            onClick={(e) => {
               // Ensure the picker opens when clicking anywhere on the input
               const target = e.target as HTMLInputElement;
               target.showPicker?.();
            }}
            className="w-full min-w-0 px-4 py-3 border-2 border-gray-300 rounded-lg bg-white text-base text-gray-900 transition-all duration-300 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500 hover:border-gray-400 cursor-pointer"
         />
      </div>
   );
};

export default DateTimeInput;
