
LIBRARY ieee;
USE ieee.std_logic_1164.ALL;
USE std.textio.all;
use ieee.std_logic_textio.all;
USE ieee.numeric_std.ALL;

use ieee.math_real.all;

ENTITY string2number IS
END string2number;

ARCHITECTURE behavioral OF string2number IS

    function CharToInt(c : character) return integer is
        begin
            case c is
                when '0' => return 0;
                when '1' => return 1;
                when '2' => return 2;
                when '3' => return 3;
                when '4' => return 4;
                when '5' => return 5;
                when '6' => return 6;
                when '7' => return 7;
                when '8' => return 8;
                when '9' => return 9;
                when others => report "Invalid character : " & c severity failure;
                               return 0;
            end case;
        end function;


    function StringToInteger(s : string) return integer is
        variable result  : integer := 0;
        variable my_sign : integer := 1;
    begin
        for i in s'range loop
            if s(i) = '-' then
                my_sign := -1;
            elsif s(i) = '+' then
                my_sign := 1;
            elsif s(i) >= '0' and s(i) <= '9' then
                result := result * 10 + CharToInt(s(i));
            else
                -- Handle invalid characters in the string
                report "Invalid character in the string: " & s(i) severity failure;
            end if;
        end loop;
        result := my_sign * result;
        return result;
    end function;


    function StringToReal(s : string) return real is
        variable result    : real := 0.0;
        variable my_sign   : real := 1.0;
        variable frac_part : boolean := false;
        variable frac_exp  : real := 0.1;
    begin
        for i in s'range loop
            if s(i) = '-' then
                my_sign := -1.0;
            elsif s(i) = '+' then
                my_sign := 1.0;
            elsif s(i) = '.' then
                frac_part := true;
            elsif s(i) >= '0' and s(i) <= '9' then
                if frac_part then
                    result := result + frac_exp * real(CharToInt(s(i)));
                    frac_exp := frac_exp / 10.0;
                else
                    result := result * 10.0 + real(CharToInt(s(i)));
                end if;
            else
                -- Handle invalid characters in the string
                report "Invalid character in the string: " & s(i) severity failure;
            end if;
        end loop;
        result := my_sign * result;
        return result;
    end function;
    
begin


process
    variable my_integer : integer;
    variable my_real    : real;
begin
    my_integer := StringToInteger("0");
    report "Converted Integer: 0 -> " & integer'image(my_integer) severity note;

    my_integer := StringToInteger("12345");
    report "Converted Integer: 12345 -> " & integer'image(my_integer) severity note;
   
    my_integer := StringToInteger("-12345");
    report "Converted Integer: -12345 -> " & integer'image(my_integer) severity note;
   
    my_integer := StringToInteger("+12345");
    report "Converted Integer: +12345 -> " & integer'image(my_integer) severity note;

    my_integer := StringToInteger("2147483647");
    report "Converted Integer: 2147483647 -> " & integer'image(my_integer) severity note;
    
    my_integer := StringToInteger("-2147483648");
    report "Converted Integer: -2147483648 -> " & integer'image(my_integer) severity note;
    
    my_integer := StringToInteger("2147483648");
    report "FAILING converting Integer: 2147483648 -> " & integer'image(my_integer) severity note;




    my_real := StringToReal("0");
    report "Converted Real: 0 -> " & to_string(my_real, "%.40f") severity note;

    my_real := StringToReal("1");
    report "Converted Real: 1 -> " & to_string(my_real, "%.40f") severity note;

    my_real := StringToReal("1.0");
    report "Converted Real: 1.0 -> " & to_string(my_real, "%.40f") severity note;

    my_real := StringToReal("1.1");
    report "Converted Real: 1.1 -> " & to_string(my_real, "%.40f") severity note;

    my_real := StringToReal("-1");
    report "Converted Real: -1 -> " & to_string(my_real, "%.40f") severity note;

    my_real := StringToReal("-1.1");
    report "Converted Real: -1.1 -> " & to_string(my_real, "%.40f") severity note;

    my_real := StringToReal("10");
    report "Converted Real: 10 -> " & to_string(my_real, "%.40f") severity note;

    my_real := StringToReal("123456789.123456789");
    report "Converted Real: 123456789.123456789 -> " & to_string(my_real, "%.40f") severity note;

    my_real := StringToReal("12345678901234567890");
    report "Converted Real: 12345678901234567890 -> " & to_string(my_real, "%.40f") severity note;

    my_real := StringToReal("0.00000123");
    report "Converted Real: 0.00000123 -> " & to_string(my_real, "%.40f") severity note;

    my_real := StringToReal("0.0000000000000123");
    report "Converted Real: 0.0000000000000123 -> " & to_string(my_real, "%.40f") severity note;

    my_real := StringToReal("0.0000000000000000000000000000000123");
    report "Converted Real: 0.0000000000000000000000000000000123 -> " & to_string(my_real, "%.40f") severity note;

   wait;
end process;



end behavioral;
