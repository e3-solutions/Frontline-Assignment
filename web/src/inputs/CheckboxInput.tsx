import React from "react";

interface CheckboxInputProps {
   label: string;
   name: string;
   checked: boolean;
   required?: boolean;
   hint?: string;
   onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

const CheckboxInput: React.FC<CheckboxInputProps> = ({
   label,
   name,
   checked = false,
   required = false,
   hint,
   onChange,
}) => {
   return (
      <div className="form-group mb-4 flex items-center gap-3 min-w-[200px]">
         <input
            type="checkbox"
            id={name}
            name={name}
            checked={checked}
            required={required}
            onChange={onChange}
            className="mt-1 h-5 w-5 rounded border-2 border-gray-300 bg-white text-blue-600 transition-all duration-200 focus:ring-2 focus:ring-blue-500 focus:ring-offset-0 cursor-pointer"
         />
         <label
            htmlFor={name}
            className="flex-1 text-sm font-semibold text-gray-800 cursor-pointer select-none"
         >
            {label}
            {hint && <span className="ml-1 font-normal text-gray-600">{hint}</span>}
         </label>
      </div>
   );
};

export default CheckboxInput;
