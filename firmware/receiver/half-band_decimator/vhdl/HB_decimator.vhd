-------------------------------------------------------------------------------
--
-- Copyright (C) 2023
-- Station de Radioastronomie de Nançay,
-- Observatoire de Paris, PSL Research University, CNRS, Univ. Orléans, OSUC,
-- 18330 Nançay, France
--
--
-- This program is free software: you can redistribute it and/or modify
-- it under the terms of the GNU General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU General Public License for more details.
--
-- You should have received a copy of the GNU General Public License
-- along with this program.  If not, see <http://www.gnu.org/licenses/>.
--
-------------------------------------------------------------------------------
-- Author: Cedric Viou (cedric.viou@obs-nancay.fr)
--
-- Description: Half-band decimator filter
-- 
--
-------------------------------------------------------------------------------

LIBRARY ieee;
USE ieee.std_logic_1164.ALL;
USE std.textio.all;
use ieee.std_logic_textio.all;
USE ieee.numeric_std.ALL;

use ieee.math_real.all;

ENTITY HB_decimator IS
  GENERIC (
    g_nof_data_path  : integer :=  2;  -- Number of channels (polarisations included)
    g_din_w          : integer := 18;
    g_din_dp         : integer := 17;
    g_nof_mult_stage : integer :=  4;
    g_coef_list      : string  := "";
    g_coef_w         : integer := 18;
    g_coef_dp        : integer := 17;
    g_acc_w          : integer := 48;
    g_acc_dp         : integer := 40;
    g_dout_w         : integer := 18;                             
    g_dout_dp        : integer := 17                             
  );
  PORT (
    rst            : IN  std_logic := '0';
    clk            : IN  std_logic;
    ce             : IN  std_logic;
  
    sync_in        : IN  std_logic;  -- used as reset in CASPER toolflow
    sync_out       : OUT std_logic;
    
    data_in_slv    : IN  std_logic_vector((g_nof_data_path * g_din_w)-1 downto 0);
    data_in_valid  : IN  std_logic;

    data_out_slv   : OUT std_logic_vector((g_nof_data_path * g_dout_w)-1 downto 0);
    data_out_valid : OUT std_logic
  );
END HB_decimator;

ARCHITECTURE behavioral OF HB_decimator IS
    type real_array is array(natural range <>) of real;
    constant Nof_Coefficients : natural := 3 + g_nof_mult_stage * 4;  -- 3 central coefficients + 2 0's + 2 non-zeros coefficients

    constant sync_delay_value : natural := 100;  -- FIXME
    type sync_delay_t is array(sync_delay_value-1 downto 0) of std_logic;
    signal sync_delay_line : sync_delay_t := (others => '0');  -- no reset for this one
    signal got_sync        : std_logic;
    
    function ToRealArray(CoefficientsString : string; Nof_Coefficients : natural) return real_array is 
        variable Coefficients : real_array(0 to Nof_Coefficients-1);
	variable start_idx : natural := 1;
        variable end_idx : natural := 1;
    begin
        for coef_idx in 0 to Nof_Coefficients-1 loop
            -- search for separating space or end of string
            while end_idx <= CoefficientsString'length loop
                if CoefficientsString(end_idx) = ' ' then
                    exit;
                end if;
                end_idx := end_idx + 1;
            end loop;

            Coefficients(coef_idx) := real'value(CoefficientsString(start_idx to end_idx-1));
            start_idx := end_idx + 1;
            end_idx := start_idx + 1;
        end loop;
	return Coefficients;
    end ToRealArray;

    constant CoefficientsReal : real_array(0 to Nof_Coefficients-1) := ToRealArray(g_coef_list, Nof_Coefficients);

    type signed_array is array(natural range <>) of signed(g_coef_w-1 downto 0);

    function ToSignedArray(CoefficientsReal : real_array;
                           coef_w : natural;
                           coef_dp : natural) return signed_array is 
        variable Coefficients : signed_array(CoefficientsReal'range);
    begin
	    for coef_idx in CoefficientsReal'range loop
            Coefficients(coef_idx) := to_signed(integer(CoefficientsReal(coef_idx) * (2.0**real(coef_dp))), coef_w);
        end loop;
        return Coefficients;
    end ToSignedArray;

    constant CoefficientsSigned : signed_array(0 to Nof_Coefficients-1) := ToSignedArray(CoefficientsReal, g_coef_w, g_coef_dp);

    type data_in_path_t is array(0 to g_nof_data_path-1) of signed(g_din_w-1 downto 0);
    signal data_in   : data_in_path_t;
    signal data_in_r : data_in_path_t;

    type data_in_demuxed_path_t is array(0 to 1) of data_in_path_t;
    signal data_in_demuxed       : data_in_demuxed_path_t;
    signal data_in_demuxed_valid : std_logic;
    signal odd_sample           : std_logic;




    type data_out_path_t is array(0 to g_nof_data_path-1) of signed(g_dout_w-1 downto 0);
    signal data_out : data_out_path_t;

BEGIN

    coef_test: process
    begin
        -- Print the converted real array to check the result
        for i in CoefficientsReal'range loop
            report "Coefficient(" & integer'image(i) & ") = "
                    & real'image(CoefficientsReal(i)) & " (real) = " 
                    & integer'image(to_integer(CoefficientsSigned(i))) & " (signed Q(" & integer'image(g_coef_w) & "," & integer'image(g_coef_dp) & "))";
        end loop;
        wait;
    end process;


    sync_delay: process(clk)
    begin
        if rst = '1' then
            got_sync <= '0';
        elsif rising_edge(clk) then
            if data_in_valid = '1' then
                sync_delay_line <= got_sync & sync_delay_line(sync_delay_value-1 downto 1);
                got_sync <= '0';
            end if;
            if sync_in = '1' then
                got_sync <= '1';
            end if;
        end if;
    end process;
    sync_out <= sync_delay_line(0);



    data_in_slv2signed: process(data_in_slv)
    begin
        for dp_idx in 0 to g_nof_data_path-1 loop
            data_in(dp_idx) <= signed(data_in_slv(((dp_idx+1)*g_din_w)-1 downto dp_idx*g_din_w));
        end loop;
    end process;

    din_demux: process(clk)
    begin
        if rst = '1' or sync_in = '1'then
            odd_sample <= '0';
            data_in_r <= (others => (others => '0'));
            data_in_demuxed <= (others => (others => (others => '0')));
        elsif rising_edge(clk) then
            data_in_demuxed_valid <= '0';
            if data_in_valid = '1' then
                if odd_sample = '0' then
                    data_in_r <= data_in;
                else
                    data_in_demuxed <= data_in_r & data_in;
                    data_in_demuxed_valid <= '1';
                end if;
                odd_sample <= not odd_sample;
            end if;
            if sync_in = '1' then
                odd_sample <= '0';
                data_in_r <= (others => (others => '0'));
                data_in_demuxed <= (others => (others => (others => '0')));
            end if;
        end if;
    end process;



    data_out <= (others => (others => '0'));
    data_out_valid <= '0';

    data_out_signed2slv: process(data_out)
    begin
        for dp_idx in 0 to g_nof_data_path-1 loop
            data_out_slv(((dp_idx+1)*g_din_w)-1 downto dp_idx*g_din_w) <= std_logic_vector(data_out(dp_idx));
        end loop;
    end process;

END behavioral;
