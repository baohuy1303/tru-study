export default function ChatArea() {
  return (
    <div className="flex-1 flex flex-col items-center justify-end p-8 w-full max-w-4xl mx-auto h-full space-y-8 min-h-0">
      <div className="flex-1 w-full flex flex-col justify-center items-center text-center opacity-80 shrink-0">
        <h2 className="text-4xl font-semibold text-[#08060d] dark:text-[#f3f4f6] tracking-tight m-0 mb-3">
          What do you want to learn today?
        </h2>
        <p className="text-lg text-[#6b6375] dark:text-[#9ca3af] m-0">
          Select course materials on the left to get started.
        </p>
      </div>

      <div className="w-full relative shadow-[0_8px_30px_rgb(0,0,0,0.12)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.4)] rounded-2xl shrink-0 border border-transparent dark:border-[#2e303a]">
        <input 
          type="text" 
          placeholder="Ask anything about your courses..."
          className="w-full px-6 py-5 rounded-2xl bg-white dark:bg-[#1f2028] text-[#08060d] dark:text-[#f3f4f6] focus:outline-none focus:ring-2 focus:ring-[#aa3bff] dark:focus:ring-[#c084fc] transition-all text-lg mb-0 font-sans"
        />
        <button className="absolute right-4 top-1/2 transform -translate-y-1/2 p-2.5 bg-[#aa3bff] hover:bg-[#9922ff] dark:bg-[#c084fc] dark:hover:bg-[#a855f7] text-white dark:text-[#08060d] rounded-xl shadow-md transition-colors cursor-pointer border-none flex items-center justify-center">
          <svg className="w-6 h-6 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
    </div>
  );
}
