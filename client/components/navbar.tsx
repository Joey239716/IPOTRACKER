"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Menu, X, Settings, Search } from "lucide-react";
import { supabase } from "@/lib/supabase-client";
import { useSearch } from "@/lib/search-context";
import type { User } from "@supabase/supabase-js"; // ✅ use official Supabase User type

const navItems = [
  { label: "Home", href: "/" },
  { label: "Watchlist", href: "/watchlist" },
];

export default function Navbar() {
  const pathname = usePathname();
  const { query, setQuery } = useSearch();
  const [isOpen, setIsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [user, setUser] = useState<User | null>(null); // ✅ no more `any`
  const [showLogoutModal, setShowLogoutModal] = useState(false);

  useEffect(() => {
    // Initialize theme preference
    const stored = localStorage.getItem("theme");
    const isDark =
      stored === "dark" ||
      (!stored && window.matchMedia("(prefers-color-scheme: dark)").matches);
    setDarkMode(isDark);
    document.documentElement.classList.toggle("dark", isDark);

    // Fetch logged-in user
    const fetchUser = async () => {
      const { data } = await supabase.auth.getUser();
      setUser(data.user ?? null);
    };
    fetchUser();
  }, []);

  const toggleDarkMode = () => {
    const next = !darkMode;
    setDarkMode(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  const handleLogout = async () => {
    setShowLogoutModal(true);
    try {
      await supabase.auth.signOut();
      setUser(null);
      // Keep modal visible briefly before redirect
      setTimeout(() => {
        setShowLogoutModal(false);
        window.location.href = "/";
      }, 500);
    } catch (err: unknown) {
      if (err instanceof Error) {
        console.error("Logout failed:", err.message);
      } else {
        console.error("Logout failed:", err);
      }
      setShowLogoutModal(false);
    }
  };

  return (
    <nav className="sticky top-0 z-50 select-none">
      {/* Navbar */}
      <div className="bg-white dark:bg-[#1c2333] border-b border-gray-200 dark:border-[#252f3e] transition-colors">
        <div className="max-w-7xl 2xl:max-w-screen-2xl mx-auto px-2">
          <div className="flex items-center h-16 gap-6">
            <Link
              href="/"
              className="flex items-center space-x-2 text-2xl font-bold text-gray-900 dark:text-white"
            >
              <img
                src="/logo.png"
                alt="IPO Street Logo"
                className="w-10 h-10 object-contain"
              />
              <span>IPO Street</span>
            </Link>

            {/* Search bar — grows to fill space between logo and nav links */}
            {pathname === "/" && (
              <div className="hidden md:block relative flex-1 max-w-sm">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search company or ticker..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-sm bg-gray-50 dark:bg-[#252f3e] border border-gray-200 dark:border-[#2e3a4e] rounded-lg text-slate-700 dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-100 caret-auto select-text"
                />
              </div>
            )}

            {/* Nav links + settings + auth — pushed to far right with ml-auto */}
            <div className="hidden md:flex items-center gap-4 ml-auto">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`text-base font-medium select-none caret-transparent focus:outline-none whitespace-nowrap ${
                    pathname === item.href
                      ? "text-blue-600 dark:text-blue-400"
                      : "text-gray-700 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400"
                  }`}
                >
                  {item.label}
                </Link>
              ))}

              {/* ⚙️ Settings dropdown */}
              <div className="relative">
                <button
                  onClick={() => setSettingsOpen(!settingsOpen)}
                  className="group relative inline-flex items-center justify-center overflow-hidden rounded-md border border-neutral-200 dark:border-gray-500 bg-transparent px-1.5 py-1 font-medium text-neutral-600 dark:text-neutral-300 transition-all hover:bg-[#eeeeee] dark:hover:bg-neutral-700 select-none focus:outline-none [box-shadow:0px_4px_1px_#d4d4d4] dark:[box-shadow:0px_4px_1px_#838383] active:translate-y-[2px] active:shadow-none pb-1.5 pt-0.5"
                >
                  <Settings size={16} />
                </button>

                {settingsOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setSettingsOpen(false)} />
                    <div className="absolute right-0 mt-2 w-48 bg-white dark:bg-[#1c2333] border border-gray-200 dark:border-[#252f3e] rounded-md shadow-lg z-50">
                      <div className="block px-4 py-2 text-sm text-gray-400 dark:text-gray-500 cursor-not-allowed select-none">
                        <div className="flex items-center justify-between">
                          <span>Profile</span>
                          <span className="text-xs italic">Coming Soon</span>
                        </div>
                      </div>
                      <div className="block px-4 py-2 text-sm text-gray-400 dark:text-gray-500 cursor-not-allowed select-none">
                        <div className="flex items-center justify-between">
                          <span>Account</span>
                          <span className="text-xs italic">Coming Soon</span>
                        </div>
                      </div>
                      <div className="flex items-center justify-between px-4 py-2 hover:bg-gray-100 dark:hover:bg-[#252f3e] select-none">
                        <span className="text-sm text-gray-700 dark:text-slate-200">Dark Mode</span>
                        <label className="relative inline-flex items-center cursor-pointer select-none">
                          <input type="checkbox" className="sr-only peer" checked={darkMode} onChange={toggleDarkMode} />
                          <div className="w-10 h-5 bg-gray-200 peer-focus:ring-2 peer-focus:ring-blue-300 dark:bg-[#252f3e] rounded-full peer peer-checked:bg-blue-600 transition-colors" />
                          <div className="absolute left-0.5 bg-white w-4 h-4 rounded-full transition-transform peer-checked:translate-x-5" />
                        </label>
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* 🔐 Auth Buttons */}
              {user ? (
                <button
                  onClick={handleLogout}
                  className="group relative inline-flex items-center justify-center overflow-hidden rounded-md border border-[#0356a8] dark:border-gray-500 bg-[#0466c8] text-white px-1.5 text-xs font-medium transition-all hover:bg-[#0356a8] select-none caret-transparent focus:outline-none cursor-pointer [box-shadow:0px_4px_1px_#034b8f] active:translate-y-[2px] active:shadow-none pb-1.5 pt-0.5"
                >
                  Log Out
                </button>
              ) : (
                <>
                  <Link
                    href="/login"
                    className="group relative inline-flex items-center justify-center overflow-hidden rounded-md border border-neutral-200 dark:border-gray-500 bg-transparent px-1.5 text-xs font-medium text-neutral-600 dark:text-neutral-300 transition-all hover:bg-[#eeeeee] dark:hover:bg-neutral-700 select-none caret-transparent focus:outline-none cursor-pointer [box-shadow:0px_4px_1px_#d4d4d4] dark:[box-shadow:0px_4px_1px_#838383] active:translate-y-[2px] active:shadow-none pb-1.5 pt-0.5"
                  >
                    Log In
                  </Link>
                  <Link
                    href="/signup"
                    className="group relative inline-flex items-center justify-center overflow-hidden rounded-md border border-[#0356a8] dark:border-gray-500 bg-[#0466c8] text-white px-1.5 text-xs font-medium transition-all hover:bg-[#0356a8] select-none caret-transparent focus:outline-none cursor-pointer [box-shadow:0px_4px_1px_#034b8f] active:translate-y-[2px] active:shadow-none pb-1.5 pt-0.5"
                  >
                    Sign Up
                  </Link>
                </>
              )}
            </div>

            {/* 📱 Mobile menu toggle */}
            <div className="md:hidden ml-auto">
              <button
                onClick={() => setIsOpen(!isOpen)}
                className="p-2 rounded-md focus:outline-none focus:ring select-none"
                aria-label="Toggle menu"
              >
                {isOpen ? (
                  <X size={24} className="text-gray-800 dark:text-gray-100" />
                ) : (
                  <Menu size={24} className="text-gray-800 dark:text-gray-100" />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* 📱 Mobile dropdown */}
        {isOpen && (
          <div className="md:hidden px-4 pb-4 bg-white dark:bg-[#1c2333] space-y-3">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setIsOpen(false)}
                className={`block px-4 py-2 rounded-md select-none caret-transparent focus:outline-none ${
                  pathname === item.href
                    ? "bg-blue-50 dark:bg-[#252f3e] text-blue-600"
                    : "text-gray-700 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-[#252f3e]"
                }`}
              >
                {item.label}
              </Link>
            ))}

            <hr className="border-t border-gray-300 dark:border-[#252f3e]" />

            {/* 🌙 Dark mode toggle (mobile) */}
            <div className="flex items-center justify-between px-4 py-2 hover:bg-gray-100 dark:hover:bg-[#252f3e] select-none">
              <span className="text-sm text-gray-700 dark:text-slate-200">
                Dark Mode
              </span>
              <label className="relative inline-flex items-center cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="sr-only peer"
                  checked={darkMode}
                  onChange={toggleDarkMode}
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:ring-2 peer-focus:ring-blue-300 dark:bg-[#252f3e] rounded-full peer peer-checked:bg-blue-600 transition-colors" />
                <div className="absolute left-1 top-1 bg-white w-4 h-4 rounded-full transition-transform peer-checked:translate-x-5" />
              </label>
            </div>

            {/* 🔐 Auth Buttons (mobile) */}
            {user ? (
              <button
                onClick={() => {
                  handleLogout();
                  setIsOpen(false);
                }}
                className="block w-full text-left px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 select-none"
              >
                Log Out
              </button>
            ) : (
              <>
                <Link
                  href="/login"
                  onClick={() => setIsOpen(false)}
                  className="block px-4 py-2 rounded-md select-none text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
                >
                  Log In
                </Link>
                <Link
                  href="/signup"
                  onClick={() => setIsOpen(false)}
                  className="block px-4 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 select-none"
                >
                  Sign Up
                </Link>
              </>
            )}
          </div>
        )}
      </div>

      {/* ✅ Logout Success Modal */}
      {showLogoutModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black bg-opacity-50">
          <div className="relative w-[90%] max-w-sm rounded-lg border border-gray-200 dark:border-[#252f3e] p-6 shadow-xl bg-white dark:bg-[#161b27] text-gray-800 dark:text-slate-100 transform transition-all duration-300 ease-out">
            <div className="flex flex-col items-center">
              <div className="w-16 h-16 flex items-center justify-center bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 rounded-full mb-4">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="w-8 h-8"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">
                Logging Out...
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 text-center">
                You have been logged out of your account.
              </p>
              <div className="mt-4">
                <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
              </div>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
