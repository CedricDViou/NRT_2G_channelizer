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
USE ieee.numeric_std.ALL;
use ieee.math_real.all;
USE std.textio.all;

ENTITY HB_decimator_tb IS
  GENERIC (
      g_nof_data_path  : integer :=  2;  -- Number of channels (polarisations included)
      g_din_w          : integer := 18;
      g_din_dp         : integer := 17;
      g_nof_coef       : integer := 19;
      g_coef_list      : string  := "-1 -0.1 0.1 0.999984741 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 0.10 0.11 0.12 0.13 0.14 0.15 0.16";
      g_coef_w         : integer := 18;
      g_coef_dp        : integer := 17;
      g_acc_w          : integer := 48;
      g_acc_dp         : integer := 40;
      g_dout_w         : integer := 18;                             
      g_dout_dp        : integer := 17
  );                             
END HB_decimator_tb;

ARCHITECTURE behavioral OF HB_decimator_tb IS

  signal SIM_RUNNING    : boolean := True;

  signal clk            : std_logic := '1';
  signal rst            : std_logic;

  signal sync_in        : std_logic;
  signal sync_out       : std_logic;

  signal data_in        : std_logic_vector((g_nof_data_path * g_din_w)-1 downto 0);
  signal data_in_valid  : std_logic;
  signal RANDOM_DV_IN   : boolean := False;   -- Random pause between single datavalid


  signal data_out       : std_logic_vector((g_nof_data_path * g_dout_w)-1 downto 0);
  signal data_out_valid : std_logic;

  procedure RandomWait(
    signal clk : in std_logic;
    constant MIN_DELAY : integer := 0;
    constant MAX_DELAY : integer := 10;
    variable seed1, seed2 : inout integer
  ) is
        variable random_value : real;
        variable delay_value : natural;
    begin
        uniform(seed1, seed2, random_value);
        delay_value := integer(round(random_value * real(MAX_DELAY - MIN_DELAY) + real(MIN_DELAY)));
        --report "Delay=" & real'image(random_value) & " = " & natural'image(delay_value);
        for ck in 0 to delay_value-1 loop
            wait until rising_edge(clk);
        end loop;
  end procedure;


BEGIN

  clk <= not clk after 2.5 ns;
  rst <= '1', '0' after 20 ns;

  sync_in_gen: process
  begin
    sync_in <= '0';
    wait for 50 ns;
    wait until rising_edge(clk);
    sync_in <= '1';
    wait until rising_edge(clk);
    sync_in <= '0';
    wait;
  end process;

  RANDOM_DV_IN <= False, True after 1 us;

  data_in_source: process
    file input_file : TEXT;
    variable fstatus: FILE_OPEN_STATUS;
    variable L : LINE;
    variable sample : integer;
    variable seed1, seed2 : integer := 999;
  begin
    data_in <= (others => '0');
    data_in_valid <= '0';

    file_open(fstatus, input_file, "./counter.txt", read_mode);
    -- g_nof_data_path = 2
    -- x = np.arange(1, 0x100, dtype=np.int64).reshape((-1,1))
    -- x = np.hstack((x, x + 0x100))
    -- np.savetxt('counter.txt', x, fmt='%10d')
    
    -- file_open(fstatus, input_file, "../design/noise_and_2_lines_input.txt", read_mode);

    wait until sync_in = '1' and rising_edge(clk);

    while (not EndFile (input_file)) loop
        readline(input_file, L);
        for dp_idx in 0 to g_nof_data_path-1 loop
            read(L, sample);
            data_in(((dp_idx+1)*g_din_w)-1 downto dp_idx*g_din_w) <= std_logic_vector( to_signed(sample, g_din_w) );
        end loop;
        data_in_valid <= '1';
        wait until rising_edge(clk);
        data_in_valid <= '0';
        if RANDOM_DV_IN then RandomWait(clk, 0, 2, seed1, seed2); end if;
    end loop;

    data_in_valid <= '0';
    file_close(input_file);

    wait for 1 us;
    SIM_RUNNING <= False;
    wait for 20 ns;
    assert false report "End of simulation!!!!" severity failure ;
    wait;
  end process;



  uut: entity work.HB_decimator
    GENERIC MAP(
      g_nof_data_path  => g_nof_data_path ,
      g_din_w          => g_din_w         ,
      g_din_dp         => g_din_dp        ,
      g_nof_coef       => g_nof_coef      ,
      g_coef_list      => g_coef_list     ,
      g_coef_w         => g_coef_w        ,
      g_coef_dp        => g_coef_dp       ,
      g_acc_w          => g_acc_w         ,
      g_acc_dp         => g_acc_dp        ,
      g_dout_w         => g_dout_w        ,
      g_dout_dp        => g_dout_dp       
    )
    PORT MAP(
      rst            => rst           ,
      clk            => clk           ,
      ce             => '1'           ,
      sync_in        => sync_in       ,
      sync_out       => sync_out      ,
      data_in_slv    => data_in       ,
      data_in_valid  => data_in_valid ,
      data_out_slv   => data_out      ,
      data_out_valid => data_out_valid
    );


  data_out_source: process
    file output_file : TEXT;
    variable fstatus: FILE_OPEN_STATUS;
    variable L : LINE;
    variable sample : integer;
  begin
    file_open(fstatus, output_file, "../design/noise_and_2_lines_output.txt", write_mode);
    wait until sync_out = '1' and rising_edge(clk);

    while SIM_RUNNING loop
        if data_out_valid = '1' then
            for dp_idx in 0 to g_nof_data_path-1 loop
                sample := to_integer(signed(data_out(((dp_idx+1)*g_din_w)-1 downto dp_idx*g_din_w)));
                write(L, sample);
            end loop;
            writeline(output_file, L);
        end if;
        wait until rising_edge(clk);
    end loop;

    file_close(output_file);
  wait;
  end process;






END behavioral;
