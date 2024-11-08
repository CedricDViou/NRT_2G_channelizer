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
    g_SIMULATION     : boolean := false;
    g_nof_data_path  : integer :=  2;  -- Number of channels (polarisations included)
    g_din_w          : integer := 18;
    g_din_dp         : integer := 17;
    g_nof_coef       : integer := -1;
    g_coef_list      : string  := "";
    g_coef_w         : integer := 20;
    g_coef_dp        : integer := 17;
    g_acc_w          : integer := 48;
    g_acc_dp         : integer := 34;
    g_dout_w         : integer := 18;
    g_dout_dp        : integer := 17

    -- generated with ../design/quantif_analysis.py
    --                    11111                   1111111111222222222233333 
    --                    43210987654321.1234567890123456789012345678901234 
    -- din     Q(18,17): |             _._________________                 |
    -- pre_add Q(19,17): |            __._________________                 |
    -- coef    Q(20,17): |           ___._________________                 |
    -- mult    Q(39,34): |         _____.__________________________________|
    -- acc     Q(48,34): |______________.__________________________________|
    -- dout    Q(18,17): |             _._________________                 |
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
begin
    -- Check that g_nof_coef = 3 + (2+2) * M;  -- 3 central coefficients + 2 0's + 2 non-zeros coefficients
    assert (real(g_nof_coef) - 3.0) mod 4.0 = 0.0 report "g_nof_coef is NOT of the form 3 + (2+2) * M, with M in natural numbers" severity failure;
END HB_decimator;

ARCHITECTURE behavioral OF HB_decimator IS

    -- Delay line for Sync signal
    constant c_sync_delay_value : natural := 100;  -- FIXME
    type sync_delay_t is array(c_sync_delay_value-1 downto 0) of std_logic;
    signal sync_delay_line : sync_delay_t := (others => '0');  -- no reset for this one
    signal got_sync        : std_logic;


    -- Convert g_coef_list string into a list of reals
    type real_array is array(natural range <>) of real;

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


    function ToRealArray(InputString : string) return real_array is
        constant c_max_nof_real : natural := (InputString'length + 1) / 2;  -- at least one char and one space per real -> no need to allocate more space
        variable reals : real_array(0 to c_max_nof_real-1);
        variable nof_reals     : natural := 0;
	    variable start_idx : natural := 1;
        variable end_idx : natural := 1;
    begin
        while start_idx < InputString'length+1 loop
            -- search for separating space or end of string
            while end_idx <= InputString'length loop
                if InputString(end_idx) = ' ' then
                    exit;
                end if;
                end_idx := end_idx + 1;
            end loop;

            -- NOT supported by Vivado
            --reals(nof_reals) := real'value(InputString(start_idx to end_idx-1));
            reals(nof_reals) := StringToReal(InputString(start_idx to end_idx-1));
            nof_reals := nof_reals + 1;
            start_idx := end_idx + 1;
            end_idx := start_idx + 1;
        end loop;
	    return reals(0 to nof_reals-1);
    end ToRealArray;

    constant c_CoefficientsReal : real_array := ToRealArray(g_coef_list);


    -- Convert a list of reals into a list of signed
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

    -- Filter coefficients: h[n], with n \in [0, g_nof_coef[
    constant c_CoefficientsSigned : signed_array := ToSignedArray(c_CoefficientsReal, g_coef_w, g_coef_dp);


    -- Signals used to demux the input streams
    type data_in_path_t is array(0 to g_nof_data_path-1) of signed(g_din_w-1 downto 0);
    signal data_in   : data_in_path_t;
    signal data_in_r : data_in_path_t;

    type data_in_demuxed_path_t is array(0 to 1) of data_in_path_t;
    signal data_in_demuxed       : data_in_demuxed_path_t;
    signal data_in_demuxed_valid : std_logic;
    signal odd_sample           : std_logic;


    -- Constant and signals for subfilters (see ../design/AMD_FIR_Compiler_Half-Band_Decimator.pdf for notations)
    --   Top arm: h_0[n] = a_0, a_2, a_4, ... a_(2i)
    --     Since filter coefficients are symetrical, we use a pre-adder structure to save multipliers
    --   Bottom arm: h_1[n] = 0, 0, ..., 1, ..., 0, 0

    -- Top arm computations:
    constant c_top_delay_line_length : natural := (g_nof_coef-1)/2;
    type top_delay_line_t is array(0 to c_top_delay_line_length-1) of data_in_path_t;
    signal top_delay_line : top_delay_line_t;

    constant c_nof_mult       : natural := (g_nof_coef+1)/4;
    constant c_max_nof_adder  : natural := c_nof_mult/2 + (c_nof_mult mod 2);  -- add an extra adder to store delay line in case of dangling input
    constant c_add_tree_depth : natural := natural(ceil(log2(real(c_nof_mult))));

    type pre_adders_path_t is array(0 to g_nof_data_path-1) of signed(g_din_w+1-1          downto 0);
    type mults_path_t      is array(0 to g_nof_data_path-1) of signed(g_din_w+1+g_coef_w-1 downto 0);
    type accs_path_t       is array(0 to g_nof_data_path-1) of signed(g_acc_w-1            downto 0);

    type pre_adders_t is array(0 to c_nof_mult-1) of pre_adders_path_t;
    type mults_t      is array(0 to c_nof_mult-1) of mults_path_t;
    type accs_level_t is array(0 to c_max_nof_adder-1) of accs_path_t;
    type accs_t       is array(0 to c_add_tree_depth-1) of accs_level_t;

    signal pre_adders : pre_adders_t;
    signal mults      : mults_t;
    signal accs       : accs_t;


    function is_even(val: integer) return boolean is
    begin
        if val mod 2 = 0 then
            return True;
        else
            return False;
        end if;
    end is_even;


    function is_odd(val: integer) return boolean is
    begin
        return not is_even(val);
    end is_odd;
       

    function getTopArmCoefficients(CoefficientsSigned : real_array) return real_array is
        constant nof_top_coef : natural := (CoefficientsSigned'length + 1)/4;
        variable Coefficients : real_array(0 to nof_top_coef-1);
    begin
	    for coef_idx in Coefficients'range loop
            Coefficients(coef_idx) := CoefficientsSigned(2 * coef_idx);
        end loop;
        return Coefficients;
    end getTopArmCoefficients;

    constant c_TopArmCoefficientsReal : real_array(0 to c_nof_mult-1) := getTopArmCoefficients(c_CoefficientsReal);
    constant c_TopArmCoefficientsSigned : signed_array(0 to c_nof_mult-1) := ToSignedArray(c_TopArmCoefficientsReal, g_coef_w, g_coef_dp);


    -- Bottom arm computations:
    -- Bottom arm is a simple delay line of length of half the bottom arm filter to feed a multiplication by the central coefficient (1.0, no DSP for that)
    constant c_central_coef_idx : natural := (g_nof_coef-1)/2;
    -- The delay line length is
    constant c_bottom_delay_line_length : natural := (g_nof_coef-3)/4 + 1 + c_add_tree_depth + 1;  -- +1 to compensate pre-adders located in top branch and for adders in tree adder and +1 for ???
    type bottom_delay_line_t is array(0 to c_bottom_delay_line_length-1) of data_in_path_t;
    signal bottom_delay_line : bottom_delay_line_t;

    signal bottom_out : accs_path_t;
    signal filter_out : accs_path_t;

    type data_out_path_t is array(0 to g_nof_data_path-1) of signed(g_dout_w-1 downto 0);
    signal data_out : data_out_path_t;

BEGIN

    p_coef_test: process
        variable my_severity : severity_level := failure;
    begin
        if g_SIMULATION then
            my_severity := warning;
        end if;

        assert c_CoefficientsSigned'length = g_nof_coef
            report "g_coef_list """ & g_coef_list & """" &
                   " doesn't contain the expected number of coefficients (g_nof_coef=" &
                   integer'image(g_nof_coef) &
                   ").  Found " & integer'image(c_CoefficientsSigned'length) & " reals in the list"
            severity my_severity;

        -- Print the converted real array to check the result
        for i in c_CoefficientsReal'range loop
            report  "Real to signed conversion check:  "
                    & "Coefficient(" & integer'image(i) & ") = "
                    & real'image(c_CoefficientsReal(i)) & " (real) = "
                    & integer'image(to_integer(c_CoefficientsSigned(i))) & " (signed Q(" & integer'image(g_coef_w) & "," & integer'image(g_coef_dp) & "))";
        end loop;

        -- Check that filter is symetrical
        for i in 0 to c_central_coef_idx-1 loop
            assert c_CoefficientsReal(i) = c_CoefficientsReal(g_nof_coef - 1 - i)
                report "Filter symetry check:  "
                       & "h[" & integer'image(i) & "] != h[" & integer'image(g_nof_coef - 1 - i) & "]"
                       & "  ->  " & real'image(c_CoefficientsReal(i)) & " != " & real'image(c_CoefficientsReal(g_nof_coef - 1 - i))
                severity my_severity;
        end loop;

        for i in c_CoefficientsReal'range loop
            if i = c_central_coef_idx then  -- Check that central coefficent is 1
                assert c_CoefficientsReal(i) = 1.0
                    report "Central coef value check:  "
                           & "h[" & integer'image(i) & "] = " & real'image(c_CoefficientsReal(i)) & " != 1.0"
                    severity my_severity;
            elsif (i mod 2) = 1 then  -- Check that odd coefficients are 0.0 (except central one)
                assert c_CoefficientsReal(i) = 0.0
                    report "Odd coefficients should be 0.0:  "
                           & "h[" & integer'image(i) & "] = " & real'image(c_CoefficientsReal(i))
                    severity my_severity;
            end if;
        end loop;

        wait;
    end process;


    p_sync_delay: process(clk, rst)
    begin
        if rst = '1' then
            got_sync <= '0';
        elsif rising_edge(clk) then
            if data_in_valid = '1' then
                sync_delay_line <= got_sync & sync_delay_line(c_sync_delay_value-1 downto 1);
                got_sync <= '0';
            end if;
            if sync_in = '1' then
                got_sync <= '1';
            end if;
        end if;
    end process;
    sync_out <= sync_delay_line(0);



    p_data_in_slv2signed: process(data_in_slv)
    begin
        for dp_idx in 0 to g_nof_data_path-1 loop
            data_in(dp_idx) <= signed(data_in_slv(((dp_idx+1)*g_din_w)-1 downto dp_idx*g_din_w));
        end loop;
    end process;

    p_din_demux: process(clk, rst)
    begin
        if rst = '1' then
            odd_sample <= '0';
            data_in_r <= (others => (others => '0'));
            data_in_demuxed <= (others => (others => (others => '0')));
        elsif rising_edge(clk) then
            data_in_demuxed_valid <= '0';
            if data_in_valid = '1' then
                data_in_r <= data_in;
                if odd_sample = '1' then
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


    p_both_arm_filters: process(clk, rst)
        variable v_cur_nof_adder_inputs : natural;
        variable v_cur_nof_adder        : natural;
        variable v_dangling_adder_input : boolean;
    begin
        if rst = '1' then
            if g_SIMULATION then  -- do NOT reset delay lines for synthesis (SRL16 optimization)
                top_delay_line <= (others => (others => (others => '0')));
                bottom_delay_line <= (others => (others => (others => '0')));
            end if;
            pre_adders <= (others => (others => (others => '0')));
            mults      <= (others => (others => (others => '0')));
            accs       <= (others => (others => (others => (others => '0'))));
            bottom_out <= (others => (others => '0'));
            filter_out <= (others => (others => '0'));
            data_out   <= (others => (others => '0'));
            data_out_valid <= '0';
        elsif rising_edge(clk) then
            data_out_valid <= '0';
            if data_in_demuxed_valid = '1' then
              -- top branch filter
                -- delay line
                top_delay_line    <= data_in_demuxed(0) &    top_delay_line(0 to c_top_delay_line_length   -2);

                -- pre_adder
                for data_path_idx in 0 to g_nof_data_path-1 loop
                    pre_adders(0)(data_path_idx) <= resize(data_in_demuxed(0)(data_path_idx), g_din_w+1)
                                                  + resize(top_delay_line(c_top_delay_line_length-1)(data_path_idx), g_din_w+1);
                    for pre_adder_idx in 1 to c_nof_mult-1 loop
                        pre_adders(pre_adder_idx)(data_path_idx) <= resize(top_delay_line(pre_adder_idx-1)(data_path_idx), g_din_w+1)
                                                                  + resize(top_delay_line(c_top_delay_line_length-1-pre_adder_idx)(data_path_idx), g_din_w+1);
                    end loop;  --  pre_adder_idx
                end loop;  --  data_path_idx

                -- coef multiply
                for data_path_idx in 0 to g_nof_data_path-1 loop
                    for mult_idx in 0 to c_nof_mult-1 loop
                        mults(mult_idx)(data_path_idx) <= c_TopArmCoefficientsSigned(mult_idx) * pre_adders(mult_idx)(data_path_idx);
                    end loop;  --  mult_idx
                end loop;  --  data_path_idx

                -- adders/accumulator
                for data_path_idx in 0 to g_nof_data_path-1 loop
                    v_cur_nof_adder_inputs := c_nof_mult;
                    v_cur_nof_adder        := v_cur_nof_adder_inputs/2 + (v_cur_nof_adder_inputs mod 2);
                    v_dangling_adder_input := is_odd(v_cur_nof_adder_inputs);
                    for add_tree_depth in 0 to c_add_tree_depth-1 loop
                        if add_tree_depth = 0 then
                            for adder_idx in 0 to v_cur_nof_adder_inputs/2-1 loop
                                accs(add_tree_depth)(adder_idx)(data_path_idx) <= resize(mults(2*adder_idx  )(data_path_idx), g_acc_w)
                                                                                + resize(mults(2*adder_idx+1)(data_path_idx), g_acc_w);
                            end loop;  --  adder_idx

                            if v_dangling_adder_input then
                                accs(add_tree_depth)(v_cur_nof_adder-1)(data_path_idx) <= resize(mults(v_cur_nof_adder_inputs-1)(data_path_idx), g_acc_w);
                            end if;

                            v_cur_nof_adder_inputs := v_cur_nof_adder;
                            v_cur_nof_adder        := v_cur_nof_adder_inputs/2 + (v_cur_nof_adder_inputs mod 2);
                            v_dangling_adder_input := is_odd(v_cur_nof_adder_inputs);
                        else
                            for adder_idx in 0 to v_cur_nof_adder_inputs/2-1 loop
                                accs(add_tree_depth)(adder_idx)(data_path_idx) <= accs(add_tree_depth-1)(2*adder_idx  )(data_path_idx)
                                                                                + accs(add_tree_depth-1)(2*adder_idx+1)(data_path_idx);
                            end loop;  --  adder_idx

                            if v_dangling_adder_input then
                                accs(add_tree_depth)(v_cur_nof_adder-1)(data_path_idx) <= accs(add_tree_depth-1)(v_cur_nof_adder_inputs-1)(data_path_idx);
                            end if;

                            v_cur_nof_adder_inputs := v_cur_nof_adder;
                            v_cur_nof_adder        := v_cur_nof_adder_inputs/2 + (v_cur_nof_adder_inputs mod 2);
                            v_dangling_adder_input := is_odd(v_cur_nof_adder_inputs);
                        end if;
                    end loop;  -- add_tree_depth
                end loop;  -- data_path_idx

              -- bottom branch filter
                -- delay line
                bottom_delay_line <= data_in_demuxed(1) & bottom_delay_line(0 to c_bottom_delay_line_length-2);

                -- 1.0 coef multiply
                for data_path_idx in 0 to g_nof_data_path-1 loop
                    bottom_out(data_path_idx) <= shift_left(resize(bottom_delay_line(c_bottom_delay_line_length-1)(data_path_idx), g_acc_w), g_coef_dp);
                end loop;  -- data_path_idx

              -- Merge both branches
                for data_path_idx in 0 to g_nof_data_path-1 loop
                    filter_out(data_path_idx) <= accs(c_add_tree_depth-1)(0)(data_path_idx) + bottom_out(data_path_idx);
                end loop;  -- data_path_idx

              -- Convert to output format (simple truncation for now)
                for data_path_idx in 0 to g_nof_data_path-1 loop
                    data_out(data_path_idx) <= resize( shift_right(filter_out(data_path_idx), g_acc_dp-g_dout_dp), g_dout_w);
                end loop;  -- data_path_idx
                data_out_valid <= '1';

            end if;
            if sync_in = '1' then
                if g_SIMULATION then  -- do NOT reset delay lines for synthesis
                    top_delay_line <= (others => (others => (others => '0')));
                    bottom_delay_line <= (others => (others => (others => '0')));
                end if;
                pre_adders <= (others => (others => (others => '0')));
                mults      <= (others => (others => (others => '0')));
                accs       <= (others => (others => (others => (others => '0'))));
                bottom_out <= (others => (others => '0'));
                filter_out <= (others => (others => '0'));
                data_out   <= (others => (others => '0'));
                data_out_valid <= '0';
                end if;
        end if;
    end process;


    p_data_out_signed2slv: process(data_out)
    begin
        for dp_idx in 0 to g_nof_data_path-1 loop
            data_out_slv(((dp_idx+1)*g_din_w)-1 downto dp_idx*g_din_w) <= std_logic_vector(data_out(dp_idx));
        end loop;
    end process;

END behavioral;
