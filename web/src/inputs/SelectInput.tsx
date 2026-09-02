import React from "react";

interface SelectOption {
   value: string;
   label: string;
}

interface SelectInputProps {
   label: string;
   name: string;
   value?: string;
   options: SelectOption[];
   required?: boolean;
   hint?: string;
   onChange?: (e: React.ChangeEvent<HTMLSelectElement>) => void;
}

const SelectInput: React.FC<SelectInputProps> = ({
   label,
   name,
   value = "",
   options,
   required = false,
   hint,
   onChange,
}) => {
   return (
      <div className="form-group mb-6 flex flex-col justify-center min-w-[200px]">
         <label htmlFor={name} className="block text-sm font-semibold text-gray-800 mb-2 text-left">
            {label}
            {hint && <span className="text-gray-600 font-normal ml-1">{hint}</span>}
         </label>
         <select
            id={name}
            name={name}
            value={value}
            required={required}
            onChange={onChange}
            className="w-full min-w-0 px-4 py-3 border-2 border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all duration-200 text-gray-900 bg-white text-base"
         >
            <option value="">Select...</option>
            {options.map((option) => (
               <option key={option.value} value={option.value}>
                  {option.label}
               </option>
            ))}
         </select>
      </div>
   );
};

export default SelectInput;
