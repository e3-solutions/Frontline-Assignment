import React from "react";

interface SubmitButtonProps {
   children: React.ReactNode;
   loading?: boolean;
   disabled?: boolean;
   onClick?: () => void;
   type?: "button" | "submit";
}

const SubmitButton: React.FC<SubmitButtonProps> = ({
   children,
   loading = false,
   disabled = false,
   onClick,
   type = "submit",
}) => {
   return (
      <div className="button-group flex justify-center gap-4 mt-6 pt-4 border-t border-gray-100">
         <button
            type={type}
            onClick={onClick}
            disabled={disabled || loading}
            className="bg-blue-600 hover:bg-blue-700 text-white px-7 py-2.5 rounded-lg font-semibold transition-all duration-200 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-md text-base min-w-0 flex-shrink-0"
         >
            {loading && <span className="animate-spin">⟳</span>}
            {children}
         </button>
      </div>
   );
};

export default SubmitButton;
