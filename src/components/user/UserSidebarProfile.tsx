import { SelectItem, Select } from "../ui/Select";


const UserInfo = () => {
  return (
     <div className="grid w-full grid-cols-[auto_1fr] gap-x-2 rounded-md text-white">
            {/* <img className="bg-black h-8 w-8 rounded-full" src="#" alt="User avatar" /> */}
            <span className="flex flex-none row-span-2 justify-center items-center h-8 w-8 text-sm bg-[#2B2F35] text-white rounded-full">
              AM
            </span>
            <p className="text-xs col-start-2 justify-self-start">Александр Матвеев</p>
            <p className="text-[10px] col-start-2 justify-self-start">Аналитик</p>
        </div>
  )  

}

export default function UserSidebarProfile() {
  return (
    <div>
      <Select
        className="px-5"
        buttonClassName="hover:bg-zinc-800 py-2 px-2 cursor-pointer rounded-lg bg-[#222428]" 
        buttonIconClassName=""
        direction="up"
        buttonContent={   
        <UserInfo></UserInfo>
        }
      >
        {(setOpen) => (
          <>
            <SelectItem
            
              onClick={() => {
                setOpen(false);
              }}
            >
              Профиль
            </SelectItem>
            <SelectItem
            
              onClick={() => {
                setOpen(false);
              }}
            >
              Настройки
            </SelectItem>
          </>
        )}
      </Select>
    </div>
  );
}
