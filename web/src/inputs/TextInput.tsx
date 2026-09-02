import React from "react";

interface TextInputProps {
   label: string;
   name: string;
   value?: string;
   placeholder?: string;
   required?: boolean;
   hint?: string;
   type?: React.HTMLInputTypeAttribute;
   min?: number;
   max?: number;
   step?: number | string;
   inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
   prefix?: string;
   onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

const TextInput: React.FC<TextInputProps> = ({
   label,
   name,
   value = "",
   placeholder,
   required = false,
   hint,
   type = "text",
   min,
   max,
   step,
   inputMode,
   prefix,
   onChange,
}) => {
   const baseInputClasses =
      "min-w-0 px-4 py-2.5 text-base text-gray-900 placeholder-gray-400 outline-none transition-all duration-200";
   const prefixedInputClasses = baseInputClasses.replace("px-4 py-2.5", "px-3 py-2.5");

   return (
      <div className="form-group mb-4 flex flex-col justify-center min-w-[200px]">
         <label
            htmlFor={name}
            className="mb-1.5 block text-left text-sm font-semibold text-gray-800"
         >
            {label}
            {hint && <span className="ml-1 font-normal text-gray-600">{hint}</span>}
         </label>
         {prefix ? (
            <div className="flex items-center rounded-lg border-2 border-gray-300 bg-white transition-all duration-200 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500">
               <span className="pl-3 pr-2 text-sm font-semibold text-gray-500">{prefix}</span>
               <input
                  type={type}
                  id={name}
                  name={name}
                  value={value}
                  placeholder={placeholder}
                  required={required}
                  onChange={onChange}
                  min={min}
                  max={max}
                  step={step}
                  inputMode={inputMode}
                  className={`w-full border-l border-gray-200 bg-transparent ${prefixedInputClasses}`}
               />
            </div>
         ) : (
            <input
               type={type}
               id={name}
               name={name}
               value={value}
               placeholder={placeholder}
               required={required}
               onChange={onChange}
               min={min}
               max={max}
               step={step}
               inputMode={inputMode}
               className={`w-full rounded-lg border-2 border-gray-300 bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-500 ${baseInputClasses}`}
            />
         )}
      </div>
   );
};

export default TextInput;
