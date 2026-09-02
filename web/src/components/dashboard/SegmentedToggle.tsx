type ToggleOption = {
   id: "loads" | "calls";
   label: string;
};

const options: ToggleOption[] = [
   { id: "loads", label: "Loads" },
   { id: "calls", label: "Calls" },
];

type SegmentedToggleProps = {
   active: "loads" | "calls";
   onChange: (value: "loads" | "calls") => void;
};

export function SegmentedToggle({ active, onChange }: SegmentedToggleProps) {
   return (
      <div className="relative inline-flex rounded-lg border border-slate-200 bg-slate-100 p-1 text-sm">
         {options.map((item) => {
            const isActive = active === item.id;
            return (
               <button
                  key={item.id}
                  type="button"
                  onClick={() => onChange(item.id)}
                  className={`relative rounded-md px-5 py-2 transition-all duration-150 ${
                     isActive
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-500 hover:text-slate-700"
                  }`}
               >
                  {item.label}
               </button>
            );
         })}
      </div>
   );
}
