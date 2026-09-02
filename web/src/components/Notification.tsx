import React, { useEffect } from "react";

type NotificationType = "success" | "error";

interface NotificationProps {
	type: NotificationType;
	message: string;
	onClose: () => void;
}

export default function Notification({ type, message, onClose }: NotificationProps) {
	useEffect(() => {
		const timer = setTimeout(() => {
			onClose();
		}, 5000);

		return () => clearTimeout(timer);
	}, [onClose]);

	const bgColor = type === "success" ? "bg-green-50" : "bg-red-50";
	const borderColor = type === "success" ? "border-green-200" : "border-red-200";
	const textColor = type === "success" ? "text-green-800" : "text-red-800";
	const iconColor = type === "success" ? "text-green-600" : "text-red-600";
	const icon = type === "success" ? "✓" : "✕";

	return (
		<div
			className={`fixed top-4 right-4 z-50 flex items-center gap-3 px-4 py-3 rounded-lg border-2 ${bgColor} ${borderColor} shadow-lg max-w-md transition-all duration-300 ease-in-out`}
			style={{ animation: "slideInRight 0.3s ease" }}
		>
			<span className={`text-xl font-bold ${iconColor}`}>{icon}</span>
			<p className={`flex-1 text-sm font-medium ${textColor}`}>{message}</p>
			<button
				onClick={onClose}
				className={`text-lg font-bold ${textColor} hover:opacity-70 transition-opacity`}
			>
				×
			</button>
		</div>
	);
}
